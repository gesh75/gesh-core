"""SQL REAL counts truncate via int() — 4.9 vs 2.1 is still net 2 and passes."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_float_counts_truncate_then_apply_net_floor():
    row = {
        "verdict": "BUY",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": 1,
            "Volume": 1,
            "Macro": 1,
        },
        "bullish": 4.9,
        "bearish": 2.1,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False
    assert d.reason == ""


def test_float_counts_net_one_blocks():
    row = {
        "verdict": "BUY",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": 1,
            "Volume": 1,
            "Macro": 1,
        },
        "bullish": 3.9,
        "bearish": 2.1,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "net" in d.reason.lower()
