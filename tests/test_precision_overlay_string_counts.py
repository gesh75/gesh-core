"""SQL/JSON string counts still coerce via int() for the net-vote floor."""

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


def test_string_counts_net_two_passes():
    d = precision_overlay_blocks("BUY", _row("4", "2"))
    assert d.blocked is False


def test_string_counts_majority_bearish_blocks():
    d = precision_overlay_blocks("BUY", _row("2", "4"))
    assert d.blocked is True
    assert "majority" in d.reason.lower() or "net" in d.reason.lower()
