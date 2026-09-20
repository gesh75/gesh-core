"""A poisoned stop must fail even when the other level is a valid price."""

from __future__ import annotations

import pytest

from gesh_core.trading.contract import TradeIntent


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_stop_rejected_when_take_profit_valid(bad):
    problems = TradeIntent(
        symbol="NVDA",
        action="BUY",
        confidence=1.0,
        source="m",
        target_position_pct=0.02,
        stop_loss=bad,
        take_profit=120.0,
    ).validate()
    assert any("stop_loss must be > 0" in p for p in problems)
    assert not any("take_profit must be > 0" in p for p in problems)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_take_profit_rejected_when_stop_valid(bad):
    problems = TradeIntent(
        symbol="NVDA",
        action="BUY",
        confidence=1.0,
        source="m",
        target_position_pct=0.02,
        stop_loss=90.0,
        take_profit=bad,
    ).validate()
    assert any("take_profit must be > 0" in p for p in problems)
    assert not any("stop_loss must be > 0" in p for p in problems)
