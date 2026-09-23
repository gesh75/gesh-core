"""PAPER CASH_FLOOR uses cfg.paper_cash_usd even when the live snapshot is NaN."""

from __future__ import annotations

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def test_paper_mode_ignores_nan_account_cash():
    cfg = RiskConfig(paper_mode=True, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    portfolio = {"equity_summary": {"cash": float("nan"), "portfolio_equity": 50_000.0}}
    # 100_000 - 0.02 * 50_000 = 99_000
    assert _post_trade_cash_estimate(portfolio, intent, cfg) == 99_000.0
