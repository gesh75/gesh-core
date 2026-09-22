"""None / True action is not exact BUY, so a Rel.Strength veto never runs."""

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


def test_none_and_true_action_fail_open():
    row = _rs_bearish_row()
    assert precision_overlay_blocks("BUY", row).blocked is True
    for action in (None, True, False, 1):
        d = precision_overlay_blocks(action, row)
        assert d.blocked is False, action
        assert d.reason == ""
