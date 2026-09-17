"""Leftover CASH_FLOOR math: equity is the debit base, not cash.

#83 pins missing/junk LIVE cash. A non-numeric portfolio_equity must still
surface (not silently debit $0), and a measured $0 book must not invent a
debit from target_pct × equity.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def test_live_junk_portfolio_equity_raises() -> None:
    cfg = RiskConfig(paper_mode=False, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    portfolio = {
        "equity_summary": {"cash": 10_000.0, "portfolio_equity": "N/A"},
    }
    with pytest.raises((TypeError, ValueError)):
        _post_trade_cash_estimate(portfolio, intent, cfg)


def test_zero_equity_buy_does_not_debit_cash() -> None:
    cfg = RiskConfig(paper_mode=True, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    portfolio = {"equity_summary": {"cash": 1.0, "portfolio_equity": 0}}
    post = _post_trade_cash_estimate(portfolio, intent, cfg)
    assert post == pytest.approx(100_000.0)
