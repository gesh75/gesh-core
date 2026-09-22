"""JSON-string Macro='-1' is not == -1, so the Macro veto does not fire."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_string_macro_does_not_veto():
    row = {
        "verdict": "BUY",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": 1,
            "Volume": 1,
            "Macro": "-1",
        },
        "bullish": 4,
        "bearish": 1,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False
    assert d.reason == ""
