"""JSON/YAML often decode -1 as -1.0 — that must still fire the Rel.Strength veto."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_float_minus_one_rel_strength_blocks():
    row = {
        "verdict": "BUY",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": -1.0,
            "Volume": 1,
            "Macro": 1,
        },
        "bullish": 4,
        "bearish": 1,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "Rel.Strength" in d.reason
