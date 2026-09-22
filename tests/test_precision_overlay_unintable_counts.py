"""List/dict/blank counts are present and non-None, so int() crashes the overlay."""

from __future__ import annotations

import pytest

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


def test_empty_string_counts_raise_value_error():
    with pytest.raises(ValueError, match="invalid literal"):
        precision_overlay_blocks("BUY", _row("", 0))


@pytest.mark.parametrize("bad", [[], {}, [1, 2]])
def test_container_counts_raise_type_error(bad):
    with pytest.raises(TypeError):
        precision_overlay_blocks("BUY", _row(bad, 0))
