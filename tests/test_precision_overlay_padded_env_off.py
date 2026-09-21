"""Disable tokens still win after strip+lower — launchd padding must turn the overlay off."""

from __future__ import annotations

import pytest

from gesh_core.trading.autopilot_core import precision_overlay_blocks


@pytest.mark.parametrize("flag", [" 0 ", " FALSE ", " Off ", "\toff\n"])
def test_padded_disable_env_fails_open(monkeypatch, flag):
    monkeypatch.setenv("PRECISION_OVERLAY", flag)
    row = {
        "verdict": "BUY",
        "votes": {"Momentum": 1, "Trend": 1, "Rel.Strength": -1, "Macro": 1},
        "bullish": 4,
        "bearish": 1,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False
    assert d.reason == ""
