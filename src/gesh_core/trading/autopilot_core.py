"""Shared autopilot building blocks (PR8 phase 1 — the drift-prone fragments).

Both repos carry a full autopilot orchestrator, and three fragments have now
drifted (and bitten) independently across the copies:

  * the P2 entry-conviction floor (raw_score gate on NEW long entries),
  * the restart-safe pre-market candidate marker,
  * the stop-sweep SELL intent (whose product copy was once malformed —
    no target_position_pct — and silently gate-rejected every emergency exit).

Centralize the PURE logic here; each repo's autopilot remains the scheduler /
orchestrator and supplies its own I/O (markers table, snapshot, gate, broker).
Phase 2 (full job-body extraction) is deliberately separate — the engine copy
is live and accumulating the autonomy-gate sample.
"""
from __future__ import annotations

import json
import math
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .contract import TradeIntent

# Job-marker key for the 08:30 → 09:35 candidate handoff.
CANDIDATE_MARKER = "premarket_candidates"


def entry_floor_blocks(action: str, raw_score: float | None, min_entry_score: float) -> bool:
    """True when a NEW long entry must be dropped (P2 entry-conviction floor).

    Consensus `confidence` is DATA COVERAGE (nodes-voted fraction), not signal
    strength — alone it let near-coin-flip weighted scores trade. The floor
    gates BUYs on the consensus raw_score instead. SELL is a managed exit and
    is NEVER gated; HOLD never reaches execution.

    Non-finite scores fail closed: ``NaN < floor`` is False in IEEE-754, which
    would otherwise let a missing consensus number through as a new long.
    JSON-null / unparseable scores must not TypeError the rest of the book.
    """
    if action != "BUY":
        return False
    # Narrow None before float(): mypy rejects float(None), and JSON-null is
    # the production trigger (key present, value null — .get(..., 0) misses it).
    if raw_score is None:
        return True
    try:
        score = float(raw_score)
        floor = float(min_entry_score)
    except (TypeError, ValueError):
        return True
    if not math.isfinite(score) or not math.isfinite(floor):
        return True
    return score < floor


def candidates_marker_json(symbols: Iterable[str], today_et: str) -> str:
    """Serialize today's candidate symbols for the job-marker table."""
    return json.dumps({"date": today_et, "symbols": sorted(symbols)})


def restore_candidate_symbols(raw: str | None, today_et: str) -> list[str]:
    """Candidate symbols from a marker payload — TODAY's only, else empty.

    A process restart between the pre-market scan and the open window wipes the
    in-memory candidate dict; only same-day markers may reseed it (open_window
    re-runs consensus fresh, so symbols are all that matters). Malformed or
    stale payloads restore nothing.
    """
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, dict) or data.get("date") != today_et:
        return []
    symbols = data.get("symbols")
    if not isinstance(symbols, list):
        return []
    return [s for s in symbols if isinstance(s, str) and s]


def stop_sweep_intent(symbol: str, price: float, stop: float, book: str) -> TradeIntent:
    """Full-close SELL for a breached stop — ALWAYS gate-valid by construction.

    `target_position_pct=0.0` is load-bearing: a SELL without it fails
    TradeIntent.validate() and the risk gate rejects the emergency exit as
    malformed (the product repo shipped exactly that bug). `book` labels the
    origin ("paper" | "live") in the rationale for the audit trail.
    """
    return TradeIntent(
        symbol=symbol.upper(),
        action="SELL",
        confidence=1.0,
        source="stop_sweep",
        target_position_pct=0.0,
        rationale=f"EOD stop-loss breach ({book}): price={price:.2f} stop={stop:.2f}",
    )


@dataclass(frozen=True)
class OverlayDecision:
    """Result of the win-priority precision overlay."""

    blocked: bool
    reason: str = ""


def precision_overlay_blocks(action: str, row: Any = None) -> OverlayDecision:
    """Second-stage precision overlay on consensus BUYs.

    Vetoes BUY entries on:
      1. Rel.Strength == -1 (highest-IC node) even on STRONG BUY.
      2. Price confirmation failed: neither Momentum nor Trend is bullish (+1),
         when either node is present in votes.
      3. Net bullish votes (bullish - bearish) < 2 or bearish > bullish.
      4. Macro == -1 unless verdict is STRONG BUY and Rel.Strength == 1.

    Pure. No I/O. SELL/HOLD are never blocked.
    Missing/empty votes fail OPEN (the score floor still applies).
    Disabled when environment PRECISION_OVERLAY in {'0', 'false', 'off'}.
    """
    if action != "BUY":
        return OverlayDecision(False, "")

    if not row or not isinstance(row, dict):
        return OverlayDecision(False, "")

    flag = os.getenv("PRECISION_OVERLAY", "1").strip().lower()
    if flag in {"0", "false", "off"}:
        return OverlayDecision(False, "")

    votes = row.get("votes")
    if votes is None or not isinstance(votes, dict) or not votes:
        return OverlayDecision(False, "")

    # 1. Rel.Strength veto
    if votes.get("Rel.Strength") == -1:
        return OverlayDecision(True, "Rel.Strength is bearish (-1)")

    # 2. Price confirmation (Momentum or Trend must confirm)
    if "Momentum" in votes or "Trend" in votes:
        if votes.get("Momentum") != 1 and votes.get("Trend") != 1:
            return OverlayDecision(
                True,
                "Price confirmation failed: neither Momentum nor Trend is bullish (+1)",
            )

    # 3. Net votes / majority floor
    if "bullish" in row and "bearish" in row and row["bullish"] is not None and row["bearish"] is not None:
        bullish = int(row["bullish"])
        bearish = int(row["bearish"])
    else:
        bullish = sum(1 for v in votes.values() if v == 1)
        bearish = sum(1 for v in votes.values() if v == -1)

    if bearish > bullish:
        return OverlayDecision(True, f"Majority is bearish: {bearish} bears > {bullish} bulls")

    if (bullish - bearish) < 2:
        return OverlayDecision(True, f"Net bullish votes below threshold: {bullish - bearish} < 2")

    # 4. Macro bearish veto
    if votes.get("Macro") == -1:
        verdict = str(row.get("verdict", "") or row.get("action", "")).upper()
        if verdict == "STRONG BUY" and votes.get("Rel.Strength") == 1:
            pass
        else:
            return OverlayDecision(True, "Macro is bearish (-1)")

    return OverlayDecision(False, "")

