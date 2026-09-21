"""A partial bullish/bearish pair is ignored — vote values are counted instead."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def _votes(*, extra_bear: bool) -> dict:
    votes = {
        "Momentum": 1,
        "Trend": 1,
        "Rel.Strength": 1,
        "Volume": 1,
        "Macro": 1,
        "Fundamentals": 0,
    }
    if extra_bear:
        votes["Volume"] = -1
        votes["Macro"] = 0
        votes["Fundamentals"] = -1
    return votes


def test_bullish_only_falls_back_to_vote_count():
    """bullish=8 without bearish must not skip the net floor if votes are split."""
    row = {"verdict": "BUY", "votes": _votes(extra_bear=True), "bullish": 8}
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "net" in d.reason.lower() or "majority" in d.reason.lower()


def test_none_bearish_falls_back_to_vote_count():
    votes = _votes(extra_bear=False)
    row = {"verdict": "BUY", "votes": votes, "bullish": 1, "bearish": None}
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False
    assert d.reason == ""
