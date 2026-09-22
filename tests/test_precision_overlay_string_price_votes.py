"""JSON-string Momentum/Trend never equal int 1, so price confirmation fails."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_string_price_votes_fail_confirmation():
    row = {
        "verdict": "BUY",
        "votes": {
            "Momentum": "1",
            "Trend": "1",
            "Rel.Strength": 1,
            "Volume": 1,
            "Macro": 1,
        },
        "bullish": 4,
        "bearish": 0,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "price confirm" in d.reason.lower() or "Momentum" in d.reason or "Trend" in d.reason
