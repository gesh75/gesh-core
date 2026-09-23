"""LIVE NaN equity makes target*equity NaN, so the post-trade cash is NaN."""

from __future__ import annotations

import math

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def test_nan_equity_turns_buy_debit_into_nan():
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    portfolio = {"equity_summary": {"cash": 10_000.0, "portfolio_equity": float("nan")}}
    post = _post_trade_cash_estimate(portfolio, intent, cfg)
    assert math.isnan(post)
