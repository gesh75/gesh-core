"""Only exact ``BUY`` is overlay-gated — padded / newline actions fail open.

Case variants are already pinned. A scanner row with ``"BUY "`` or ``"\\nBUY"``
would skip Rel.Strength veto and admit a new long the score floor already
passed.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def _rs_bearish_row() -> dict:
    return {
        "verdict": "BUY",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": -1,
            "Volume": 1,
            "Macro": 1,
        },
        "bullish": 4,
        "bearish": 1,
    }


@pytest.mark.parametrize("action", ["BUY ", " BUY", "BUY\n", "\tBUY", "BUY\t"])
def test_padded_buy_fails_open_even_when_rel_strength_bearish(action: str) -> None:
    row = _rs_bearish_row()
    assert precision_overlay_blocks("BUY", row).blocked is True
    d = precision_overlay_blocks(action, row)
    assert d.blocked is False
    assert d.reason == ""
