"""Price confirmation fires when only one of Momentum/Trend is present and not +1."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_momentum_only_not_bullish_blocks():
    row = {
        "verdict": "BUY",
        "votes": {"Rel.Strength": 1, "Momentum": 0, "Volume": 1, "Macro": 1},
        "bullish": 4,
        "bearish": 0,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "Momentum" in d.reason or "Trend" in d.reason or "price" in d.reason.lower()


def test_trend_only_not_bullish_blocks():
    row = {
        "verdict": "BUY",
        "votes": {"Rel.Strength": 1, "Trend": -1, "Volume": 1, "Macro": 1},
        "bullish": 4,
        "bearish": 0,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "Momentum" in d.reason or "Trend" in d.reason or "price" in d.reason.lower()


def test_momentum_only_bullish_is_enough():
    row = {
        "verdict": "BUY",
        "votes": {"Rel.Strength": 1, "Momentum": 1, "Volume": 1, "Macro": 1},
        "bullish": 4,
        "bearish": 0,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False
