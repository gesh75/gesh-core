"""SELL without target_position_pct is invalid — same required-field branch as BUY."""

from __future__ import annotations

from gesh_core.trading.contract import TradeIntent


def test_sell_missing_target_is_invalid():
    problems = TradeIntent(
        symbol="NVDA",
        action="SELL",
        confidence=1.0,
        source="manual",
        target_position_pct=None,
    ).validate()
    assert any("require target_position_pct" in p for p in problems)
