"""The P2 entry floor is BUY-only — ADD / TRIM / EXECUTE must never be dropped.

``entry_floor_blocks`` is the shared conviction gate. SELL is already pinned
on main. Hosts that map Kelly TRIM/ADD or a non-canonical EXECUTE through the
same helper must keep those actions ungated even at a deeply negative score.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.autopilot_core import entry_floor_blocks


@pytest.mark.parametrize("action", ["ADD", "TRIM", "SELL", "HOLD", "EXECUTE", ""])
def test_non_buy_actions_never_blocked_by_entry_floor(action):
    assert entry_floor_blocks(action, raw_score=-99.0, min_entry_score=0.55) is False


def test_buy_still_blocked_below_floor():
    assert entry_floor_blocks("BUY", raw_score=-99.0, min_entry_score=0.55) is True
