"""Macro exception requires verdict ``STRONG BUY`` with a space, not ``STRONG_BUY``.

``str(verdict).upper()`` does not normalize underscores. A pipeline that emits
``STRONG_BUY`` still takes the Macro veto — pin that so a later 'normalize
verdicts' change cannot silently drop the exception or widen it.
"""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_strong_buy_underscore_does_not_bypass_macro_veto() -> None:
    row = {
        "verdict": "STRONG_BUY",
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
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "Macro" in d.reason


def test_spaced_strong_buy_still_allows_macro_with_rel_strength() -> None:
    row = {
        "verdict": "STRONG BUY",
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
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False
