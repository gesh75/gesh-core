"""no/disabled/n are not disable tokens — the Rel.Strength veto stays live."""

from __future__ import annotations

import pytest

from gesh_core.trading.autopilot_core import precision_overlay_blocks


@pytest.mark.parametrize("flag", ["no", "NO", "disabled", "n", "f"])
def test_common_disable_aliases_keep_overlay_armed(monkeypatch, flag):
    monkeypatch.setenv("PRECISION_OVERLAY", flag)
    row = {
        "verdict": "BUY",
        "votes": {"Momentum": 1, "Trend": 1, "Rel.Strength": -1, "Macro": 1},
        "bullish": 4,
        "bearish": 1,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "Rel.Strength" in d.reason
