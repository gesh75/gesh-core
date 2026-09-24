"""Macro == -1.0 (float) must veto the same as the int -1.

Scan rows persist votes as REAL. ``-1.0 == -1`` is True, so the Macro rule
still fires. Pin the float so a later ``is -1`` identity check cannot fail-open
bearish macro on STRONG-BUY-ineligible names.
"""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_macro_minus_one_point_zero_blocks_plain_buy() -> None:
    row = {
        "verdict": "BUY",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": 1,
            "Volume": 1,
            "Macro": -1.0,
        },
        "bullish": 4,
        "bearish": 1,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "Macro" in d.reason
