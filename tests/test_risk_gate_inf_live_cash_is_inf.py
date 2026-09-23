"""LIVE +inf cash stays +inf after a BUY debit — CASH_FLOOR never trips."""

from __future__ import annotations

import math

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def test_inf_live_cash_estimate_is_inf():
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    portfolio = {"equity_summary": {"cash": float("inf"), "portfolio_equity": 50_000.0}}
    post = _post_trade_cash_estimate(portfolio, intent, cfg)
    assert math.isinf(post) and post > 0
