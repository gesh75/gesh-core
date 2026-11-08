"""CASH_FLOOR debit edges for BUY intents with a falsy target weight.

``_post_trade_cash_estimate`` only subtracts ``target_position_pct * equity``
when the action is BUY *and* the target is truthy. ``0`` and ``None`` therefore
leave cash unchanged — the same path SELL uses. Pinning that keeps a later
'fix' from silently debiting (or failing) on close-to-zero BUY sizes.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def _pf(cash: float, equity: float) -> dict:
    return {"equity_summary": {"cash": cash, "portfolio_equity": equity}}


def test_buy_with_none_target_does_not_debit() -> None:
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=None)
    post = _post_trade_cash_estimate(_pf(cash=10_000.0, equity=50_000.0), intent, cfg)
    assert post == pytest.approx(10_000.0)


def test_buy_with_zero_target_does_not_debit() -> None:
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.0)
    post = _post_trade_cash_estimate(_pf(cash=10_000.0, equity=50_000.0), intent, cfg)
    assert post == pytest.approx(10_000.0)


def test_buy_with_positive_target_still_debits() -> None:
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    post = _post_trade_cash_estimate(_pf(cash=10_000.0, equity=50_000.0), intent, cfg)
    assert post == pytest.approx(9_000.0)


def test_paper_mode_still_uses_simulated_cash_when_target_missing() -> None:
    cfg = RiskConfig(paper_mode=True, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=None)
    post = _post_trade_cash_estimate(_pf(cash=300.0, equity=50_000.0), intent, cfg)
    assert post == pytest.approx(100_000.0)
