"""BUY with target_position_pct=None is falsy — CASH_FLOOR must not invent a debit."""

from __future__ import annotations

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import TradeIntent
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def test_buy_none_target_leaves_cash_unchanged():
    cfg = RiskConfig(paper_mode=False)
    intent = TradeIntent(
        symbol="NVDA",
        action="BUY",
        confidence=1.0,
        source="m",
        target_position_pct=None,
    )
    portfolio = {"equity_summary": {"cash": 10_000.0, "portfolio_equity": 50_000.0}}
    assert _post_trade_cash_estimate(portfolio, intent, cfg) == 10_000.0
