"""Owner daily-analysis-chain adapter (Phase 4B).

Translates the host ``run_ai2.py`` ``engine_results`` payload into normalized
ledger inputs and delegates to :func:`record_analysis_decision`. Every piece of
host-payload field knowledge lives in this module — the core orchestration
layer never sees ``average_buy_price``, ``consensus`` verdicts, or
``run_manifest`` internals.

Authoritative recommendation-symbol universe:
  (a) every symbol in ``engine_results["consensus"]`` whose entry carries a
      usable verdict — recorded with ``decision_type="consensus"`` and
      ``action = verdict`` (the consensus verdict is the only deterministic
      per-symbol action; ``holdings_analysis`` items have no action field), and
  (b) every ``ai_result.portfolio_recommendations`` item with
      ``category == "DIVERSIFICATION"`` and a valid symbol — recorded with
      ``decision_type="advisory"``.

Nothing is silently dropped: every exclusion is reported in
``DailyAnalysisRecording.skipped`` with a machine-readable reason.
Symbol-less portfolio-level prose recommendations (no category, no symbol) are
intentionally not recorded; they remain available in
``analysis_runs.result_json``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from gesh_core.ledger.integration import (
    DecisionInput,
    LedgerRecording,
    LedgerValidationError,
    PortfolioInput,
    QuoteInput,
    normalize_timestamp_utc,
    record_analysis_decision,
)

__all__ = [
    "DailyAnalysisRecording",
    "SkippedDecision",
    "record_daily_analysis_decision",
]

_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")
# Cash is a scalar in equity_summary, never a position. These pseudo-symbols
# are cash representations seen in host payloads, not tradable instruments.
_CASH_LIKE_SYMBOLS = frozenset({"CASH", "USD"})
_CASH_LIKE_PREFIXES = ("CUR:",)

# Only these keys leave the host payloads and enter ledger storage/hashes.
# Raw payloads are never canonicalized wholesale: an unrelated secret-named key
# (token, api_key, ...) must neither be stored nor break recording.
_CONSENSUS_ALLOWLIST = (
    "verdict",
    "raw_score",
    "confidence",
    "conviction",
    "tilt",
    "regime",
    "as_of",
)
_AI_OUTPUT_ALLOWLIST = ("verdict", "fair_value", "scores")
_SECRET_FIELD_NAMES = frozenset(
    {
        "password",
        "password_hash",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "authorization",
        "private_key",
    }
)


@dataclass(frozen=True)
class SkippedDecision:
    """A universe member that produced no recommendation row, with the reason."""

    symbol: str | None
    decision_type: str
    reason: str  # missing_symbol | invalid_symbol | cash_like_symbol |
    #              duplicate_symbol | missing_action | no_consensus_verdict


@dataclass(frozen=True)
class DailyAnalysisRecording:
    recording: LedgerRecording
    skipped: tuple[SkippedDecision, ...]


def _classify_symbol(
    raw: Any, *, blank_reason: str = "invalid_symbol"
) -> tuple[str | None, str | None]:
    """Return ``(normalized_symbol, None)`` or ``(None, skip_reason)``."""
    text = str(raw or "").strip().upper()
    if not text:
        return None, blank_reason
    if text in _CASH_LIKE_SYMBOLS or any(text.startswith(p) for p in _CASH_LIKE_PREFIXES):
        return None, "cash_like_symbol"
    if not _SYMBOL_RE.match(text):
        return None, "invalid_symbol"
    return text, None


def _finite_or_none(value: Any) -> float | None:
    """Best-effort float coercion for host data; junk/NaN/Inf becomes None."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _strip_secret_fields(value: Any) -> Any:
    """Copy a payload value while recursively removing known secret fields."""
    if isinstance(value, Mapping):
        return {
            key: _strip_secret_fields(item)
            for key, item in value.items()
            if str(key).lower() not in _SECRET_FIELD_NAMES
        }
    if isinstance(value, list):
        return [_strip_secret_fields(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_strip_secret_fields(item) for item in value)
    return value


def _allowlist(item: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {
        key: _strip_secret_fields(item[key])
        for key in keys
        if key in item and item[key] is not None
    }


def record_daily_analysis_decision(
    *,
    tenant_id: str,
    source: str,
    engine_results: Mapping[str, Any],
    analysis_run_id: int | None,
    ai_provider: str | None,
    ai_model: str | None,
    quote_provider: str | None = None,
    decision_at: datetime | str | None = None,
    db_path: Any | None = None,
) -> DailyAnalysisRecording:
    """Record the owner daily-analysis chain's decisions into the ledger.

    ``tenant_id``, ``source``, ``ai_provider`` and ``ai_model`` are explicit —
    the host passes ``OWNER_TENANT_ID`` / ``"daily_analysis_chain"`` / its real
    provider and model; nothing is inferred here. ``analysis_run_id`` is stored
    as optional metadata only (never part of a recommendation's identity).

    Timestamp precedence:
      decision_at      — explicit param, else ``ai_result_ran_at``, else raise;
      portfolio time   — ``snapshot.fetched_at``, else ``run_manifest.snapshot_as_of``;
      quote as_of      — ``run_manifest.quote_as_of[symbol]``, else NULL;
      quote retrieved  — the snapshot ``fetched_at`` (quotes arrive with the snapshot).
    All timestamps are normalized to UTC; invalid values raise
    :class:`LedgerValidationError` rather than being silently replaced.
    """
    eng = engine_results

    # ── timestamps ───────────────────────────────────────────────────────────
    decision_raw = decision_at if decision_at is not None else eng.get("ai_result_ran_at")
    if decision_raw is None:
        raise LedgerValidationError(
            "decision_at unavailable: pass decision_at or provide ai_result_ran_at"
        )
    decision_at_norm = normalize_timestamp_utc(decision_raw, field="decision_at")

    snapshot = eng.get("snapshot") or {}
    manifest = eng.get("run_manifest") or {}
    fetched_raw = snapshot.get("fetched_at") or manifest.get("snapshot_as_of")
    if fetched_raw is None:
        raise LedgerValidationError(
            "portfolio timestamp unavailable: need snapshot.fetched_at or run_manifest.snapshot_as_of"
        )
    fetched_at = normalize_timestamp_utc(fetched_raw, field="snapshot.fetched_at")
    quote_as_of_map = manifest.get("quote_as_of") or {}

    # ── portfolio (normalized + allowlisted; average_buy_price -> avg_cost) ──
    holdings_in = eng.get("holdings") or snapshot.get("holdings") or []
    holdings: list[dict[str, Any]] = []
    held_symbols: dict[str, Mapping[str, Any]] = {}
    for h in holdings_in:
        if not isinstance(h, Mapping):
            continue
        avg_cost = h.get("average_buy_price")
        if avg_cost is None:
            avg_cost = h.get("avg_cost")
        row = {
            "symbol": str(h.get("symbol") or "").strip().upper(),
            "quantity": h.get("quantity"),
            "avg_cost": avg_cost,
            "current_price": h.get("current_price", h.get("price")),
        }
        holdings.append(row)
        norm, _ = _classify_symbol(h.get("symbol"))
        if norm is not None:
            held_symbols[norm] = h

    eq = eng.get("equity_summary") or {}
    portfolio = PortfolioInput(
        holdings=holdings,
        cash=_finite_or_none(eq.get("cash")),
        buying_power=_finite_or_none(eq.get("buying_power")),
        total_equity=_finite_or_none(eq.get("total", eq.get("total_equity"))),
        captured_at=fetched_at,
        base_currency=str(eq.get("currency") or "USD"),
    )

    # ── AI per-symbol outputs (allowlisted) ──────────────────────────────────
    ai_result = eng.get("ai_result") or {}
    ha_map: dict[str, Mapping[str, Any]] = {}
    for item in ai_result.get("holdings_analysis") or []:
        if isinstance(item, Mapping):
            norm, _ = _classify_symbol(item.get("symbol"))
            if norm is not None:
                ha_map[norm] = item

    # ── decision universe ────────────────────────────────────────────────────
    decisions: list[DecisionInput] = []
    skipped: list[SkippedDecision] = []
    seen: set[tuple[str, str]] = set()
    consensus_symbols: set[str] = set()

    consensus_map = eng.get("consensus") or {}
    no_verdict_reported: set[str] = set()
    for raw_sym in sorted(consensus_map, key=lambda s: str(s).strip().upper()):
        sym, reason = _classify_symbol(raw_sym)
        if sym is None:
            skipped.append(
                SkippedDecision(
                    symbol=str(raw_sym).strip().upper() or None,
                    decision_type="consensus",
                    reason=reason or "invalid_symbol",
                )
            )
            continue
        entry = consensus_map[raw_sym]
        verdict = (
            str(entry.get("verdict") or "").strip().upper() if isinstance(entry, Mapping) else ""
        )
        if not verdict:
            skipped.append(
                SkippedDecision(
                    symbol=sym, decision_type="consensus", reason="no_consensus_verdict"
                )
            )
            no_verdict_reported.add(sym)
            continue
        consensus_symbols.add(sym)
        seen.add(("consensus", sym))
        decisions.append(
            DecisionInput(
                symbol=sym,
                decision_type="consensus",
                action=verdict,
                conviction=_finite_or_none(entry.get("conviction")),
                confidence=_finite_or_none(entry.get("confidence")),
                consensus=_allowlist(entry, _CONSENSUS_ALLOWLIST),
                ai_output=_allowlist(ha_map[sym], _AI_OUTPUT_ALLOWLIST) if sym in ha_map else None,
            )
        )

    # Holdings the engine produced no verdict for: no recommendation row (the
    # position is fully preserved in the portfolio snapshot), but never silent.
    for sym in sorted(held_symbols):
        if sym not in consensus_symbols and sym not in no_verdict_reported:
            skipped.append(
                SkippedDecision(
                    symbol=sym, decision_type="consensus", reason="no_consensus_verdict"
                )
            )

    # ── advisory (diversification radar) decisions ───────────────────────────
    for item in ai_result.get("portfolio_recommendations") or []:
        if not isinstance(item, Mapping):
            continue
        if item.get("category") != "DIVERSIFICATION":
            continue  # symbol-less portfolio-level prose: intentionally not recorded
        sym, reason = _classify_symbol(item.get("symbol"), blank_reason="missing_symbol")
        if sym is None:
            skipped.append(
                SkippedDecision(
                    symbol=None, decision_type="advisory", reason=reason or "missing_symbol"
                )
            )
            continue
        if ("advisory", sym) in seen:
            skipped.append(
                SkippedDecision(symbol=sym, decision_type="advisory", reason="duplicate_symbol")
            )
            continue
        action = str(item.get("action") or "").strip().upper()[:32]
        if not action:
            skipped.append(
                SkippedDecision(symbol=sym, decision_type="advisory", reason="missing_action")
            )
            continue
        seen.add(("advisory", sym))
        decisions.append(
            DecisionInput(
                symbol=sym,
                decision_type="advisory",
                action=action,
                ai_output=_allowlist(item, ("rationale", "priority", "category")),
            )
        )

    # ── quotes for the decision universe (never fabricate a price) ───────────
    decision_symbols = {d.symbol for d in decisions}
    quotes: list[QuoteInput] = []
    for sym in sorted(decision_symbols):
        h = held_symbols.get(sym)
        price = _finite_or_none(h.get("current_price", h.get("price"))) if h else None
        if price is not None and price <= 0:
            price = None
        as_of_raw = quote_as_of_map.get(sym)
        as_of = (
            normalize_timestamp_utc(as_of_raw, field=f"quote_as_of[{sym}]")
            if as_of_raw is not None
            else None
        )
        if price is not None:
            quotes.append(
                QuoteInput(
                    symbol=sym,
                    retrieved_at=fetched_at,
                    provider=quote_provider,
                    as_of=as_of,
                    last=price,
                    quality_state="FRESH",
                )
            )
        else:
            quotes.append(
                QuoteInput(
                    symbol=sym,
                    retrieved_at=fetched_at,
                    as_of=as_of,
                    quality_state="MISSING",
                    quality_reason="no_quote_in_payload",
                )
            )

    recording = record_analysis_decision(
        tenant_id=tenant_id,
        source=source,
        portfolio=portfolio,
        quotes=quotes,
        decisions=decisions,
        decision_at=decision_at_norm,
        ai_provider=ai_provider,
        ai_model=ai_model,
        analysis_run_id=analysis_run_id,
        db_path=db_path,
    )
    return DailyAnalysisRecording(recording=recording, skipped=tuple(skipped))
