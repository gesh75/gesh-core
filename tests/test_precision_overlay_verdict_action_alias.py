"""Macro exception reads verdict, then action — empty verdict is not STRONG BUY."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def _macro_bear_row(**extra) -> dict:
    row = {
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            "Rel.Strength": 1,
            "Volume": 1,
            "Macro": -1,
        },
        "bullish": 5,
        "bearish": 1,
    }
    row.update(extra)
    return row


def test_missing_verdict_uses_action_for_strong_buy_exception():
    row = _macro_bear_row(action="STRONG BUY")
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False


def test_empty_verdict_falls_through_to_action():
    row = _macro_bear_row(verdict="", action="STRONG BUY")
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False


def test_missing_verdict_plain_buy_action_still_blocks():
    row = _macro_bear_row(action="BUY")
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "Macro" in d.reason
