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


def _post_trade_cash_estimate(
    portfolio: dict[str, Any], intent: TradeIntent, cfg: RiskConfig
) -> float:
    """Crude estimate: cash − (target_pct × equity) for BUY; cash for SELL/other.

    In PAPER mode the available cash is the simulated cfg.paper_cash_usd, NOT the
    real account balance — otherwise paper BUYs are blocked by the real (often
    near-empty, fully-invested) Robinhood cash and no positions ever open. In LIVE
    mode the real account cash is used so the gate protects actual capital.
    (Rule #32.)
    """
    eq_summary = portfolio.get("equity_summary", {})
    cash = cfg.paper_cash_usd if cfg.paper_mode else float(eq_summary.get("cash", 0) or 0)
    equity = float(eq_summary.get("portfolio_equity", 0) or 0)
    if intent.action == "BUY" and intent.target_position_pct:
        return cash - (intent.target_position_pct * equity)
    return cash
