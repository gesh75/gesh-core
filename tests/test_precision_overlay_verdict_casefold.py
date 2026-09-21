"""Macro exception casefolds verdict — ``strong buy`` is STRONG BUY."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_lowercase_strong_buy_allows_macro_bearish():
    row = {
        "verdict": "strong buy",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": 1,
            "Volume": 1,
            "Macro": -1,
        },
        "bullish": 5,
        "bearish": 1,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False
    assert d.reason == ""
