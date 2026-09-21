"""0–0 is not a majority-bearish, but net 0 is still below the floor of 2."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_zero_zero_counts_blocked_by_net_floor():
    row = {
        "verdict": "BUY",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": 1,
            "Volume": 1,
            "Macro": 1,
        },
        "bullish": 0,
        "bearish": 0,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "net" in d.reason.lower()
    assert "0" in d.reason
