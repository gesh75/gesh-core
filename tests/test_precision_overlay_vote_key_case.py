"""Rel.Strength veto is exact-key — lowercase / screaming keys do not fire it."""

from __future__ import annotations

import pytest

from gesh_core.trading.autopilot_core import precision_overlay_blocks


@pytest.mark.parametrize("key", ["rel.strength", "REL.STRENGTH", "Rel.strength", "rs"])
def test_rel_strength_key_case_does_not_veto(key):
    row = {
        "verdict": "BUY",
        "votes": {
            "Momentum": 1,
            "Trend": 1,
            key: -1,
            "Volume": 1,
            "Macro": 1,
        },
        "bullish": 4,
        "bearish": 1,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False, key
    assert d.reason == ""
