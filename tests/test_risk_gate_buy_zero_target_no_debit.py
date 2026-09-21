"""A BUY with ``target_position_pct=0.0`` does not debit the cash estimate.

``if intent.action == "BUY" and intent.target_position_pct:`` treats 0.0 as
falsy, so the CASH_FLOOR math leaves paper/live cash unchanged. Pin that —
a later ``is not None`` check would start debiting a zero-weight BUY and
could trip the floor on a no-op intent.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def test_buy_with_zero_target_leaves_paper_cash_unchanged():
    cfg = RiskConfig(paper_mode=True, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.0)
    portfolio = {"equity_summary": {"cash": 300.0, "portfolio_equity": 50_000.0}}
    post = _post_trade_cash_estimate(portfolio, intent, cfg)
    assert post == pytest.approx(100_000.0)


def test_buy_with_zero_target_leaves_live_cash_unchanged():
    cfg = RiskConfig(paper_mode=False, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.0)
    portfolio = {"equity_summary": {"cash": 7_777.0, "portfolio_equity": 50_000.0}}
    post = _post_trade_cash_estimate(portfolio, intent, cfg)
    assert post == pytest.approx(7_777.0)
