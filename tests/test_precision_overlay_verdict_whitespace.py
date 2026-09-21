"""Padded STRONG BUY is not stripped — Macro bearish still vetoes."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_padded_strong_buy_does_not_bypass_macro_veto():
    row = {
        "verdict": " STRONG BUY ",
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
    assert d.blocked is True
    assert "Macro" in d.reason
