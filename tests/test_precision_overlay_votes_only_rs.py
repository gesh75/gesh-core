"""A lone Rel.Strength=+1 still hits the net-vote floor (1 - 0 < 2)."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_single_bullish_rel_strength_blocked_by_net_floor():
    row = {"verdict": "BUY", "votes": {"Rel.Strength": 1}}
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "net" in d.reason.lower()
