"""Blank PRECISION_OVERLAY is not a disable token — the overlay stays armed."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def _rs_bearish_row() -> dict:
    return {
        "verdict": "BUY",
        "votes": {"Momentum": 1, "Trend": 1, "Rel.Strength": -1, "Macro": 1},
        "bullish": 4,
        "bearish": 1,
    }


def test_empty_precision_overlay_env_still_blocks(monkeypatch):
    monkeypatch.setenv("PRECISION_OVERLAY", "")
    d = precision_overlay_blocks("BUY", _rs_bearish_row())
    assert d.blocked is True
    assert "Rel.Strength" in d.reason


def test_unset_precision_overlay_env_defaults_on(monkeypatch):
    monkeypatch.delenv("PRECISION_OVERLAY", raising=False)
    d = precision_overlay_blocks("BUY", _rs_bearish_row())
    assert d.blocked is True
    assert "Rel.Strength" in d.reason
