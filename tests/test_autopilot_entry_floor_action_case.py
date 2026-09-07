"""The P2 entry floor is case-sensitive on ``action``.

Only exact ``"BUY"`` is gated. Downstream paths that emit ``"buy"`` / ``"Buy"``
bypass the conviction floor and let sub-threshold longs through. SELL remains
ungated. Pin the current exact-match so a later casefold cannot silently start
blocking exits.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.autopilot_core import entry_floor_blocks


def test_canonical_buy_below_floor_is_blocked() -> None:
    assert entry_floor_blocks("BUY", 0.20, 0.35) is True


@pytest.mark.parametrize("action", ["buy", "Buy", " BUY"])
def test_noncanonical_buy_currently_bypasses_floor(action: str) -> None:
    assert entry_floor_blocks(action, 0.20, 0.35) is False


def test_sell_is_never_gated_even_at_extreme_score() -> None:
    assert entry_floor_blocks("SELL", -99.0, 0.35) is False
