"""JSON true/false counts coerce via int() — True/False is net 1, below the floor."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_bool_bullish_bearish_hit_net_floor():
    row = {
        "verdict": "BUY",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": 1,
            "Volume": 1,
            "Macro": 1,
        },
        "bullish": True,
        "bearish": False,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "net" in d.reason.lower()
