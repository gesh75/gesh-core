"""A -inf floor is non-finite and must block BUY the same as NaN."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import entry_floor_blocks


def test_negative_infinity_floor_blocks_buy():
    """``0.60 < -inf`` is False — isfinite(-inf) is what keeps the floor fail-closed."""
    assert entry_floor_blocks("BUY", 0.60, float("-inf")) is True
    assert entry_floor_blocks("SELL", 0.60, float("-inf")) is False


def test_negative_infinity_raw_score_blocks_buy():
    assert entry_floor_blocks("BUY", float("-inf"), 0.35) is True
    assert entry_floor_blocks("SELL", float("-inf"), 0.35) is False
