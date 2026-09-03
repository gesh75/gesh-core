"""HOLD must not debit the CASH_FLOOR estimate.

``_post_trade_cash_estimate`` only subtracts ``target_pct × equity`` for BUY.
HOLD is an audit/no-op action — treating it like a BUY would invent a cash
drawdown and can trip the paper/live cash floor on a day with no new entries.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def _pf(cash: float, equity: float) -> dict:
    return {"equity_summary": {"cash": cash, "portfolio_equity": equity}}


def test_hold_live_leaves_real_cash_unchanged() -> None:
    cfg = RiskConfig(paper_mode=False, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "HOLD")
    post = _post_trade_cash_estimate(_pf(cash=7_777.0, equity=50_000.0), intent, cfg)
    assert post == pytest.approx(7_777.0)


def test_hold_paper_uses_simulated_cash_not_real() -> None:
    cfg = RiskConfig(paper_mode=True, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "HOLD")
    # Real account near-empty must not leak into the paper cash estimate.
    post = _post_trade_cash_estimate(_pf(cash=300.0, equity=50_000.0), intent, cfg)
    assert post == pytest.approx(100_000.0)


def test_hold_does_not_debit_even_if_a_target_weight_is_attached() -> None:
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "HOLD", target_position_pct=0.50)
    post = _post_trade_cash_estimate(_pf(cash=10_000.0, equity=50_000.0), intent, cfg)
    assert post == pytest.approx(10_000.0)
