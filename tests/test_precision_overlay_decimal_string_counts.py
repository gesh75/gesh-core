"""Decimal-looking count strings are not int() tokens and crash the overlay."""

from __future__ import annotations

import pytest

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_decimal_string_counts_raise_value_error():
    """SQL/JSON often emits '4.9'; int('4') works, but int('4.9') does not."""
    row = {
        "verdict": "BUY",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": 1,
            "Volume": 1,
            "Macro": 1,
        },
        "bullish": "4.9",
        "bearish": "2.1",
    }
    with pytest.raises(ValueError, match="invalid literal"):
        precision_overlay_blocks("BUY", row)
