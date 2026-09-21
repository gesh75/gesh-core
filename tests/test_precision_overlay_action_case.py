"""Only exact ``BUY`` is overlay-gated — ADD/TRIM/EXECUTE and case variants fail open."""

from __future__ import annotations

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


def test_lowercase_and_managed_actions_never_blocked():
    row = _rs_bearish_row()
    assert precision_overlay_blocks("BUY", row).blocked is True
    for action in ("buy", "Buy", "ADD", "TRIM", "EXECUTE"):
        d = precision_overlay_blocks(action, row)
        assert d.blocked is False, action
        assert d.reason == ""
