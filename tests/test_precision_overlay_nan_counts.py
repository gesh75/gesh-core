"""NaN bullish/bearish hits int() and aborts the overlay instead of failing open."""

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


@pytest.mark.parametrize(
    "bullish,bearish",
    [
        (float("nan"), 1),
        (4, float("nan")),
        (float("nan"), float("nan")),
    ],
)
def test_nan_counts_raise_value_error(bullish, bearish):
    """NaN is not None, so the pair is used — int(nan) raises instead of vote fallback."""
    with pytest.raises(ValueError, match="NaN"):
        precision_overlay_blocks("BUY", _row(bullish, bearish))
