"""MIN_ENTRY_SCORE=0.0 is the documented disable for the P2 entry floor.

Config already pins that env loads as 0.0. The gate itself is only tested at
the default 0.35. A regression that treated 0.0 as "block everything below
the default" would silently drop intended weak entries; treating a slightly
negative raw_score as unblocked would let coin-flip BUYs through the bypass.
"""
from __future__ import annotations

from gesh_core.trading.autopilot_core import entry_floor_blocks


def test_zero_floor_keeps_nonnegative_buys():
    assert entry_floor_blocks("BUY", 0.0, 0.0) is False
    assert entry_floor_blocks("BUY", 0.01, 0.0) is False


def test_zero_floor_still_blocks_negative_raw_score():
    assert entry_floor_blocks("BUY", -0.01, 0.0) is True


def test_disabled_floor_never_gates_sells():
    assert entry_floor_blocks("SELL", -0.99, 0.0) is False
    assert entry_floor_blocks("HOLD", -0.99, 0.0) is False
