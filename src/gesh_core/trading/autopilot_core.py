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
from collections.abc import Iterable

from .contract import TradeIntent

# Job-marker key for the 08:30 → 09:35 candidate handoff.
CANDIDATE_MARKER = "premarket_candidates"


def entry_floor_blocks(action: str, raw_score: float | None, min_entry_score: float) -> bool:
    """True when a NEW long entry must be dropped (P2 entry-conviction floor).

    Consensus `confidence` is DATA COVERAGE (nodes-voted fraction), not signal
    strength — alone it let near-coin-flip weighted scores trade. The floor
    gates BUYs on the consensus raw_score instead. SELL is a managed exit and
    is NEVER gated; HOLD never reaches execution.
    """
    # NaN/Inf comparisons are always false, which would fail OPEN and let a
    # BUY with unknown conviction through — the exact hole this floor exists
    # to close. Non-finite floor is equally unsafe (never blocks). Hosts pass
    # consensus_row["raw_score"] here (TradeIntent does not carry it), so
    # JSON-null must not TypeError the rest of the book.
    if action != "BUY":
        return False
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
