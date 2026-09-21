"""true/on/yes/1 are not disable tokens — the Rel.Strength veto stays live."""

from __future__ import annotations

import pytest

from gesh_core.trading.autopilot_core import precision_overlay_blocks


@pytest.mark.parametrize("flag", ["1", "true", "TRUE", "on", "yes"])
def test_truthy_precision_overlay_env_still_blocks(monkeypatch, flag):
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
