"""Rel.Strength veto is a strict ``== -1`` — a string ``\"-1\"`` does not fire it."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_string_minus_one_does_not_veto_rel_strength():
    row = {
        "verdict": "BUY",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": "-1",
            "Volume": 1,
            "Macro": 1,
        },
        "bullish": 5,
        "bearish": 0,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False
    assert d.reason == ""
