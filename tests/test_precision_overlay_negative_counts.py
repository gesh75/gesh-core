"""Negative coerced counts invert the majority / net-vote floor."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def _row(bullish, bearish) -> dict:
    return {
        "verdict": "BUY",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": 1,
            "Volume": 1,
            "Macro": 1,
        },
        "bullish": bullish,
        "bearish": bearish,
    }


def test_negative_bullish_is_majority_bearish():
    """0 bears > -1 bulls — a poisoned negative bull count vetoes a healthy vote dict."""
    d = precision_overlay_blocks("BUY", _row(-1, 0))
    assert d.blocked is True
    assert "majority" in d.reason.lower()


def test_negative_bearish_inflates_net_and_passes():
    """3 - (-1) = 4, so garbage negative bears can admit a thin 3-bull row."""
    d = precision_overlay_blocks("BUY", _row(3, -1))
    assert d.blocked is False
