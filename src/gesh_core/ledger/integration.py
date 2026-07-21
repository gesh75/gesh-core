"""Recording orchestration for the GESH Decision Ledger (Phase 4B).

One recording persists exactly three kinds of objects, in this order:

1. one ``portfolio_snapshots`` row (content-addressed, idempotent),
2. zero or more ``market_quote_snapshots`` rows (content-addressed, idempotent),
3. one or more ``recommendations`` rows (append-only, deterministic IDs).

The analysis context is NOT a persisted object. It is the deterministic
``ctx_*`` hash computed over the decision inputs and stored on each
recommendation in the ``context_hash`` column.

Failure model: :func:`record_analysis_decision` either returns a successful
:class:`LedgerRecording` or raises a :class:`LedgerError` subclass. It never
returns a failure object. Hosts that want ledger failures to be non-fatal must
catch at the call site::

    try:
        recording = record_analysis_decision(...)
    except LedgerError:
        log_explicit_ledger_failure()
        continue_legacy_processing()

Writes commit per repository call, so a recording is NOT atomic across rows: a
failure mid-recording can leave a portfolio snapshot only, snapshots plus some
quote snapshots, or snapshots plus a partial recommendation set. Retrying the
same call with identical inputs converges to a complete recording because every
write is idempotent (snapshots by content hash, recommendations by
deterministic ID + content fingerprint).
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from gesh_core.ledger.canonical import content_hash
from gesh_core.ledger.hashes import (
    analysis_context_hash,
    market_quote_snapshot_hash,
    portfolio_snapshot_hash,
)
from gesh_core.ledger.repository import (
    get_recommendation,
    insert_or_get_market_quote_snapshot,
    insert_or_get_portfolio_snapshot,
    insert_recommendation,
)
from gesh_core.ledger.versions import RECOMMENDATION_ID_SCHEMA_VERSION

__all__ = [
    "DecisionInput",
    "LedgerConflictError",
    "LedgerError",
    "LedgerRecording",
    "LedgerValidationError",
    "LedgerWriteError",
    "PortfolioInput",
    "QuoteInput",
    "normalize_timestamp_utc",
    "record_analysis_decision",
    "recommendation_id_for",
]


class LedgerError(Exception):
    """Base class for ledger recording failures."""


class LedgerValidationError(LedgerError, ValueError):
    """Invalid recording input (tenant, symbol, timestamp, float, provenance)."""


class LedgerConflictError(LedgerError):
    """A recommendation_id already exists with different stored content."""


class LedgerWriteError(LedgerError):
    """A database write failed; the original error is available as ``__cause__``."""


# Symbols: uppercase tickers incl. class shares / exchange suffixes (BRK.B, RDS-A).
_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")
# Decision types: short lowercase slugs ("consensus", "advisory", ...).
_DECISION_TYPE_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,15}$")

# Stored columns compared when an insert hits a duplicate recommendation_id.
# analysis_run_id is deliberately EXCLUDED: it is optional provenance metadata,
# not decision content, so a run-id-only difference is an idempotent retry.
_FINGERPRINT_COLUMNS = (
    "action",
    "conviction",
    "confidence",
    "target_position_pct",
    "stop_price",
    "target_price",
    "consensus_json",
    "quant_summary_json",
    "ai_output_json",
    "ai_provider",
    "ai_model",
    "source",
    "decision_at",
    "context_hash",
    "portfolio_snapshot_id",
    "market_quote_snapshot_id",
)


@dataclass(frozen=True)
class PortfolioInput:
    """Normalized portfolio state for one recording.

    ``holdings`` rows use the normalized keys ``symbol``, ``quantity``,
    ``avg_cost`` (host field names are mapped by the caller/adapter).
    ``captured_at`` is required — the ledger never substitutes "now" for
    portfolio provenance.
    """

    holdings: Sequence[Mapping[str, Any]]
    cash: float | None
    buying_power: float | None
    total_equity: float | None
    captured_at: datetime | str
    base_currency: str = "USD"
    risk_state: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class QuoteInput:
    """Normalized quote observation for one symbol.

    ``retrieved_at`` is required (the column is NOT NULL). Price fields may all
    be None with ``quality_state="MISSING"`` to record that a quote was looked
    for and absent — never fabricate a price.
    """

    symbol: str
    retrieved_at: datetime | str
    asset_type: str = "equity"
    provider: str | None = None
    as_of: datetime | str | None = None
    available_time: datetime | str | None = None
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: float | None = None
    quality_state: str = "FRESH"
    quality_reason: str | None = None


@dataclass(frozen=True)
class DecisionInput:
    """One recommendation to persist.

    The recommendation links the market quote snapshot recorded for the same
    symbol in this call, or NULL when no quote was recorded for it.
    """

    symbol: str
    decision_type: str
    action: str
    conviction: float | None = None
    confidence: float | None = None
    target_position_pct: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    consensus: Mapping[str, Any] | None = None
    quant_summary: Mapping[str, Any] | None = None
    ai_output: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class LedgerRecording:
    """Result of a successful recording. Exists only on success — failures raise."""

    tenant_id: str
    source: str
    portfolio_snapshot_id: int
    portfolio_snapshot_hash: str
    market_quote_snapshot_ids: Mapping[str, int]
    context_hash: str
    recommendation_ids: tuple[str, ...]
    inserted_ids: tuple[str, ...]
    reused_ids: tuple[str, ...]


def normalize_timestamp_utc(value: datetime | str, *, field: str) -> str:
    """Normalize a datetime or ISO-8601 string to UTC ``...Z`` form.

    Naive inputs are interpreted as UTC (consistent with canonical.py). Raises
    :class:`LedgerValidationError` on empty/unparseable input — timestamps are
    never silently replaced with "now".
    """
    dt: datetime
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise LedgerValidationError(f"{field}: empty timestamp")
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:
            raise LedgerValidationError(f"{field}: invalid timestamp {value!r}") from exc
    else:
        raise LedgerValidationError(
            f"{field}: expected datetime or ISO string, got {type(value).__name__}"
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def recommendation_id_for(
    *, tenant_id: str, symbol: str, decision_type: str, context_hash: str
) -> str:
    """Deterministic recommendation identity: ``rec_<sha256>`` of the canonical
    identity payload (tenant_id, symbol, decision_type, context_hash).

    Everything else about a recommendation — including analysis_run_id — is
    stored metadata, not identity. Identical identity payloads yield identical
    IDs (idempotent retry); any difference in tenant, symbol, type, or context
    yields a different ID (full 256-bit digest, no truncation).
    """
    payload = {
        "schema_version": RECOMMENDATION_ID_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "symbol": symbol,
        "decision_type": decision_type,
        "context_hash": context_hash,
    }
    return content_hash(payload, prefix="rec")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _require_finite(value: float | None, field: str) -> float | None:
    """Reject NaN/Inf — sqlite3 would silently store NaN as NULL."""
    if value is None:
        return None
    f = float(value)
    if not math.isfinite(f):
        raise LedgerValidationError(f"{field}: non-finite value {value!r}")
    return f


def _normalize_symbol(symbol: str, *, field: str = "symbol") -> str:
    text = str(symbol).strip().upper()
    if not _SYMBOL_RE.match(text):
        raise LedgerValidationError(f"{field}: invalid symbol {symbol!r}")
    return text


def _normalize_optional_ts(value: datetime | str | None, *, field: str) -> str | None:
    if value is None:
        return None
    return normalize_timestamp_utc(value, field=field)


def _row_fingerprint(row: Mapping[str, Any]) -> str:
    """Content hash over the stored decision columns used for idempotency checks."""
    return content_hash({k: row.get(k) for k in _FINGERPRINT_COLUMNS})


def _call_repository(func: Callable[..., dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Run a repository helper, translating failures into the LedgerError hierarchy."""
    try:
        return func(**kwargs)
    except sqlite3.Error as exc:
        raise LedgerWriteError(f"{func.__name__} failed: {exc}") from exc
    except ValueError as exc:
        # Repository-level validation (blank tenant/hash, bad quality_state) and
        # CanonicalizationError from hashing are both caller-input problems.
        raise LedgerValidationError(str(exc)) from exc


def record_analysis_decision(
    *,
    tenant_id: str,
    source: str,
    portfolio: PortfolioInput,
    decisions: Sequence[DecisionInput],
    decision_at: datetime | str,
    quotes: Sequence[QuoteInput] = (),
    ai_provider: str | None = None,
    ai_model: str | None = None,
    prompt_bundle_hash: str | None = None,
    analysis_run_id: int | None = None,
    db_path: Any | None = None,
) -> LedgerRecording:
    """Persist one decision recording and return its :class:`LedgerRecording`.

    Writes, in order: the portfolio snapshot, one market quote snapshot per
    quote, then one recommendation per decision (each linked to the portfolio
    snapshot and to the quote snapshot recorded for the same symbol, if any).

    ``source`` and ``decision_at`` are required provenance — the core never
    assigns production provenance silently. ``ai_provider``/``ai_model`` stay
    NULL when the caller does not supply them. ``analysis_run_id`` is optional
    metadata with a logical, unenforced relationship to the legacy
    ``analysis_runs`` table (no FK; valid only when both sides share a DB path).

    Raises :class:`LedgerValidationError` on invalid input,
    :class:`LedgerConflictError` when a deterministic recommendation_id already
    exists with different stored content, and :class:`LedgerWriteError` on
    database failure. A failure may leave a partial recording; retrying with
    identical inputs completes it.
    """
    tenant = str(tenant_id).strip() if tenant_id else ""
    if not tenant:
        raise LedgerValidationError("tenant_id is required")
    if not source or not str(source).strip():
        raise LedgerValidationError("source is required (no default provenance)")
    source = str(source).strip()
    if not decisions:
        raise LedgerValidationError("at least one decision is required")
    decision_at_norm = normalize_timestamp_utc(decision_at, field="decision_at")

    # ── 1. portfolio snapshot ────────────────────────────────────────────────
    captured_at = normalize_timestamp_utc(portfolio.captured_at, field="portfolio.captured_at")
    cash = _require_finite(portfolio.cash, "portfolio.cash")
    buying_power = _require_finite(portfolio.buying_power, "portfolio.buying_power")
    total_equity = _require_finite(portfolio.total_equity, "portfolio.total_equity")
    ps_hash = _hash_portfolio(
        tenant,
        portfolio.holdings,
        cash,
        buying_power,
        total_equity,
        portfolio.base_currency,
        portfolio.risk_state,
    )
    ps_row = _call_repository(
        insert_or_get_portfolio_snapshot,
        tenant_id=tenant,
        snapshot_hash=ps_hash,
        holdings=list(portfolio.holdings),
        cash=cash,
        buying_power=buying_power,
        total_equity=total_equity,
        base_currency=portfolio.base_currency,
        risk_state=portfolio.risk_state,
        captured_at=captured_at,
        db_path=db_path,
    )
    ps_id = int(ps_row["id"])

    # ── 2. market quote snapshots ────────────────────────────────────────────
    mqs_ids: dict[str, int] = {}
    mqs_hashes: dict[str, str] = {}
    for q in quotes:
        sym = _normalize_symbol(q.symbol, field="quote.symbol")
        if sym in mqs_ids:
            raise LedgerValidationError(f"duplicate quote for symbol {sym!r}")
        retrieved_at = normalize_timestamp_utc(q.retrieved_at, field=f"quote[{sym}].retrieved_at")
        as_of = _normalize_optional_ts(q.as_of, field=f"quote[{sym}].as_of")
        available_time = _normalize_optional_ts(
            q.available_time, field=f"quote[{sym}].available_time"
        )
        bid = _require_finite(q.bid, f"quote[{sym}].bid")
        ask = _require_finite(q.ask, f"quote[{sym}].ask")
        last = _require_finite(q.last, f"quote[{sym}].last")
        volume = _require_finite(q.volume, f"quote[{sym}].volume")
        mqs_hash = _hash_quote(
            tenant,
            sym,
            q.asset_type,
            q.provider,
            as_of,
            available_time,
            retrieved_at,
            bid,
            ask,
            last,
            volume,
            q.quality_state,
        )
        mqs_row = _call_repository(
            insert_or_get_market_quote_snapshot,
            tenant_id=tenant,
            snapshot_hash=mqs_hash,
            symbol=sym,
            quality_state=q.quality_state,
            asset_type=q.asset_type,
            provider=q.provider,
            as_of=as_of,
            available_time=available_time,
            retrieved_at=retrieved_at,
            bid=bid,
            ask=ask,
            last=last,
            volume=volume,
            quality_reason=q.quality_reason,
            db_path=db_path,
        )
        mqs_ids[sym] = int(mqs_row["id"])
        mqs_hashes[sym] = str(mqs_row["snapshot_hash"])

    # ── 3. decision context hash (computed, not persisted) ───────────────────
    ctx = _hash_context(
        tenant,
        source,
        ps_hash,
        [mqs_hashes[s] for s in sorted(mqs_hashes)],
        ai_provider,
        ai_model,
        prompt_bundle_hash,
    )

    # ── 4. recommendations (per-row commits; partial sets possible) ──────────
    all_ids: list[str] = []
    inserted: list[str] = []
    reused: list[str] = []
    seen_ids: set[str] = set()
    for d in decisions:
        sym = _normalize_symbol(d.symbol, field="decision.symbol")
        dtype = str(d.decision_type).strip()
        if not _DECISION_TYPE_RE.match(dtype):
            raise LedgerValidationError(f"decision_type: invalid {d.decision_type!r}")
        action = str(d.action).strip()
        if not action:
            raise LedgerValidationError(f"decision {sym}/{dtype}: action is required")
        rid = recommendation_id_for(
            tenant_id=tenant, symbol=sym, decision_type=dtype, context_hash=ctx
        )
        if rid in seen_ids:
            raise LedgerValidationError(f"duplicate decision {sym}/{dtype} in this recording")
        seen_ids.add(rid)
        mqs_id = mqs_ids.get(sym)
        candidate: dict[str, Any] = {
            "action": action,
            "conviction": _require_finite(d.conviction, f"decision[{sym}].conviction"),
            "confidence": _require_finite(d.confidence, f"decision[{sym}].confidence"),
            "target_position_pct": _require_finite(
                d.target_position_pct, f"decision[{sym}].target_position_pct"
            ),
            "stop_price": _require_finite(d.stop_price, f"decision[{sym}].stop_price"),
            "target_price": _require_finite(d.target_price, f"decision[{sym}].target_price"),
            "consensus_json": _json_dumps(d.consensus) if d.consensus is not None else None,
            "quant_summary_json": _json_dumps(d.quant_summary)
            if d.quant_summary is not None
            else None,
            "ai_output_json": _json_dumps(d.ai_output) if d.ai_output is not None else None,
            "ai_provider": ai_provider,
            "ai_model": ai_model,
            "source": source,
            "decision_at": decision_at_norm,
            "context_hash": ctx,
            "portfolio_snapshot_id": ps_id,
            "market_quote_snapshot_id": mqs_id,
        }
        try:
            insert_recommendation(
                recommendation_id=rid,
                tenant_id=tenant,
                symbol=sym,
                context_hash=ctx,
                decision_at=decision_at_norm,
                source=source,
                action=candidate["action"],
                analysis_run_id=analysis_run_id,
                portfolio_snapshot_id=ps_id,
                market_quote_snapshot_id=mqs_id,
                conviction=candidate["conviction"],
                confidence=candidate["confidence"],
                target_position_pct=candidate["target_position_pct"],
                stop_price=candidate["stop_price"],
                target_price=candidate["target_price"],
                consensus=d.consensus,
                quant_summary=d.quant_summary,
                ai_output=d.ai_output,
                ai_provider=ai_provider,
                ai_model=ai_model,
                prompt_bundle_hash=prompt_bundle_hash,
                db_path=db_path,
            )
            inserted.append(rid)
        except sqlite3.IntegrityError as exc:
            existing = get_recommendation(rid, tenant_id=tenant, db_path=db_path)
            if existing is None:
                # Not a duplicate-PK conflict (e.g. FK violation) — a real write failure.
                raise LedgerWriteError(f"recommendation {rid!r} insert failed: {exc}") from exc
            if _row_fingerprint(existing) == _row_fingerprint(candidate):
                reused.append(rid)
            else:
                raise LedgerConflictError(
                    f"recommendation {rid!r} already exists with different content"
                ) from None
        except sqlite3.Error as exc:
            raise LedgerWriteError(f"recommendation {rid!r} insert failed: {exc}") from exc
        except ValueError as exc:
            raise LedgerValidationError(str(exc)) from exc
        all_ids.append(rid)

    return LedgerRecording(
        tenant_id=tenant,
        source=source,
        portfolio_snapshot_id=ps_id,
        portfolio_snapshot_hash=ps_hash,
        market_quote_snapshot_ids=mqs_ids,
        context_hash=ctx,
        recommendation_ids=tuple(all_ids),
        inserted_ids=tuple(inserted),
        reused_ids=tuple(reused),
    )


def _hash_portfolio(
    tenant: str,
    holdings: Sequence[Mapping[str, Any]],
    cash: float | None,
    buying_power: float | None,
    total_equity: float | None,
    base_currency: str,
    risk_state: Mapping[str, Any] | None,
) -> str:
    try:
        return portfolio_snapshot_hash(
            tenant_id=tenant,
            holdings=holdings,
            cash=cash,
            buying_power=buying_power,
            total_equity=total_equity,
            base_currency=base_currency,
            risk_state=risk_state,
        )
    except ValueError as exc:
        raise LedgerValidationError(f"portfolio snapshot not hashable: {exc}") from exc


def _hash_quote(
    tenant: str,
    symbol: str,
    asset_type: str,
    provider: str | None,
    as_of: str | None,
    available_time: str | None,
    retrieved_at: str,
    bid: float | None,
    ask: float | None,
    last: float | None,
    volume: float | None,
    quality_state: str,
) -> str:
    try:
        return market_quote_snapshot_hash(
            tenant_id=tenant,
            symbol=symbol,
            asset_type=asset_type,
            provider=provider,
            as_of=as_of,
            available_time=available_time,
            retrieved_at=retrieved_at,
            bid=bid,
            ask=ask,
            last=last,
            volume=volume,
            quality_state=quality_state,
        )
    except ValueError as exc:
        raise LedgerValidationError(f"quote snapshot not hashable: {exc}") from exc


def _hash_context(
    tenant: str,
    source: str,
    ps_hash: str,
    mqs_hashes: Sequence[str],
    ai_provider: str | None,
    ai_model: str | None,
    prompt_bundle_hash: str | None,
) -> str:
    try:
        return analysis_context_hash(
            tenant_id=tenant,
            source=source,
            portfolio_snapshot_hash_value=ps_hash,
            market_quote_snapshot_hashes=mqs_hashes,
            ai_provider=ai_provider,
            ai_model=ai_model,
            prompt_bundle_hash=prompt_bundle_hash,
        )
    except ValueError as exc:
        raise LedgerValidationError(f"context not hashable: {exc}") from exc
