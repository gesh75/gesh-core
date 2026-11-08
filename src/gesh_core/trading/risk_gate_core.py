"""Shared seam-free risk-gate primitives (Phase 3.5).

The two repos deliberately keep DIFFERENT gate compositions in their own
``risk_gate.evaluate()`` (the engine runs extra gates — SECTOR_CAP /
EARNINGS_PROXIMITY / LOSS_STREAK — and a stricter MARKET_REGIME). This module
holds only the primitives that are behaviorally identical AND free of the test
seams each repo monkeypatches (its module-level ``datetime`` / patched deps):

  - ``GateVerdict``               the verdict type (also imported by execution.py)
  - ``_kill_switch_present``      kill-switch file check
  - ``_post_trade_cash_estimate``CASH_FLOOR math — PAPER uses cfg.paper_cash_usd
                                  (rule #32), LIVE uses real account cash

The time- and PnL-entangled helpers (``_within_market_hours``,
``_quote_age_seconds``, ``_daily_pnl_pct``) stay in each repo's risk_gate.py
because tests freeze that module's ``datetime`` and patch its
``paper_realized_pnl_usd_today`` seam; the underlying P&L computation is already
shared via ``gesh_core.trading.state.paper_realized_pnl_usd_today``.

Pure: no broker I/O; the portfolio snapshot is passed in.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from .config import RiskConfig
from .contract import TradeIntent


@dataclass
class GateVerdict:
    approved: bool
    reason: str | None
    gates: dict[str, bool]                # gate_name → True (passed) | False (failed)
    intent_id: int                        # row id in trade_intents
    decision_id: int                      # row id in risk_decisions

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _kill_switch_present(path: str) -> bool:
    from pathlib import Path
    return Path(path).expanduser().exists()


def _finite_money(value: Any) -> float | None:
    """Coerce a snapshot/config money field to a finite float, else None.

    ``float(None)`` and ``float("N/A")`` raise, and ``float("nan")`` is truthy
    so ``value or 0`` does not catch it. A single bad equity_summary field must
    not TypeError the rest of the book (stop-sweep SELLs share this helper) or
    leak NaN into ``post_trade < min_cash`` (every NaN comparison is False, so
    CASH_FLOOR would fail open).
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _post_trade_cash_estimate(
    portfolio: dict[str, Any], intent: TradeIntent, cfg: RiskConfig
) -> float:
    """Crude estimate: cash − (target_pct × equity) for BUY; cash for SELL/other.

    In PAPER mode the available cash is the simulated cfg.paper_cash_usd, NOT the
    real account balance — otherwise paper BUYs are blocked by the real (often
    near-empty, fully-invested) Robinhood cash and no positions ever open. In LIVE
    mode the real account cash is used so the gate protects actual capital.
    (Rule #32.)

    Always returns a finite float. Unusable LIVE cash/equity (null, NaN, junk)
    fail closed on BUY — treating missing equity as $0 would make the purchase
    look free and skip the floor. SELL still returns 0 rather than raising so
    an emergency exit is not aborted by a broken snapshot field.
    """
    eq_summary = portfolio.get("equity_summary") or {}
    if not isinstance(eq_summary, dict):
        eq_summary = {}

    if cfg.paper_mode:
        cash = _finite_money(cfg.paper_cash_usd)
    else:
        raw_cash = eq_summary.get("cash", 0)
        cash = _finite_money(0 if raw_cash is None else raw_cash)

    # Absent key stays 0 (pre-existing). Explicit null/NaN/junk is unknown —
    # treating that as $0 makes target_pct × equity = 0 and the BUY looks free.
    if "portfolio_equity" in eq_summary:
        equity = _finite_money(eq_summary.get("portfolio_equity"))
    else:
        equity = 0.0
    target = _finite_money(intent.target_position_pct)

    if intent.action == "BUY" and intent.target_position_pct:
        if cash is None or equity is None or target is None:
            return 0.0
        return cash - (target * equity)
    return cash if cash is not None else 0.0
