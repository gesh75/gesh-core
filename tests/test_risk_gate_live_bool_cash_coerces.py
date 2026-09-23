"""LIVE bool cash is not rejected — True becomes $1, False is falsy and becomes $0."""

from __future__ import annotations

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def test_true_live_cash_is_one_dollar():
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    portfolio = {"equity_summary": {"cash": True, "portfolio_equity": 50_000.0}}
    # 1.0 - 0.02 * 50_000 = -999.0
    assert _post_trade_cash_estimate(portfolio, intent, cfg) == -999.0


def test_false_live_cash_is_zero_via_or_fallback():
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    portfolio = {"equity_summary": {"cash": False, "portfolio_equity": 50_000.0}}
    # False is falsy, so `False or 0` → 0.0 - 1000.0
    assert _post_trade_cash_estimate(portfolio, intent, cfg) == -1000.0
