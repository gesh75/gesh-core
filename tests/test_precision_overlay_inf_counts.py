"""±inf bullish/bearish hits int() and aborts the overlay instead of failing open."""

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
        (float("inf"), 1),
        (4, float("inf")),
        (float("-inf"), 0),
    ],
)
def test_inf_counts_raise_overflow_error(bullish, bearish):
    """Infinity is not None, so the pair is used — int(inf) raises OverflowError."""
    with pytest.raises(OverflowError, match="infinity"):
        precision_overlay_blocks("BUY", _row(bullish, bearish))
