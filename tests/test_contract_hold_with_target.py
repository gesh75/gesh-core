"""HOLD with an explicit target_position_pct is still structurally valid.

HOLD does not *require* a target, but validate() does not reject one either.
A consensus adapter that later starts attaching a residual weight to HOLD
must not start failing the risk gate solely because the field is present.
"""
from __future__ import annotations

from gesh_core.trading.contract import TradeIntent


def test_hold_with_target_pct_validates():
    intent = TradeIntent(
        symbol="NVDA",
        action="HOLD",
        confidence=0.8,
        source="consensus",
        target_position_pct=0.02,
    )
    assert intent.validate() == []


def test_hold_with_out_of_range_target_still_rejected():
    intent = TradeIntent(
        symbol="NVDA",
        action="HOLD",
        confidence=0.8,
        source="consensus",
        target_position_pct=1.5,
    )
    problems = intent.validate()
    assert any("target_position_pct must be in [0,1]" in p for p in problems)
