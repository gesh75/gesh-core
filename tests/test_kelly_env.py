"""Call-time Kelly overlay knobs — not claimed by the open Kelly PR.

Gross-exposure, correlation threshold, and cost-drag are read from the
environment on every sizing call. Garbage or a zero rebalance horizon must
fail safe; a silent raise would take down consensus / the /kelly dashboard.
"""
from __future__ import annotations

import pytest

from gesh_core import kelly


def test_max_gross_exposure_garbage_falls_back(monkeypatch):
    monkeypatch.setenv("KELLY_MAX_GROSS_PCT", "nope")
    assert kelly._max_gross_exposure() == kelly._DEFAULT_MAX_GROSS_PCT


def test_max_gross_exposure_empty_string_falls_back(monkeypatch):
    monkeypatch.setenv("KELLY_MAX_GROSS_PCT", "")
    assert kelly._max_gross_exposure() == kelly._DEFAULT_MAX_GROSS_PCT


def test_corr_threshold_garbage_falls_back(monkeypatch):
    monkeypatch.setenv("KELLY_CORR_THRESHOLD", "abc")
    assert kelly._corr_threshold() == kelly._DEFAULT_CORR_THRESHOLD


def test_cost_drag_garbage_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("KELLY_COST_BPS", "not-a-number")
    expected = (kelly._DEFAULT_COST_BPS / 10_000.0) / kelly._DEFAULT_REBALANCE_DAYS
    assert kelly._cost_drag_daily() == pytest.approx(expected)


def test_cost_drag_zero_or_negative_horizon_is_zero(monkeypatch):
    monkeypatch.setenv("KELLY_COST_BPS", "10")
    monkeypatch.setenv("KELLY_REBALANCE_DAYS", "0")
    assert kelly._cost_drag_daily() == 0.0
    monkeypatch.setenv("KELLY_REBALANCE_DAYS", "-7")
    assert kelly._cost_drag_daily() == 0.0


def test_rescale_result_is_immutable_and_reclassifies_action():
    src = {
        "optimal_pct": 10.0,
        "half_kelly": 10.0,
        "current_pct": 2.0,
        "recommended_usd": 1000.0,
        "delta_usd": 0.0,
        "delta_pct": 8.0,
        "action": "HOLD",
        "action_color": "cyan",
    }
    out = kelly._rescale_result(
        src, equity=200.0, total_portfolio=10_000.0, corr_haircut=0.5, gross_factor=1.0
    )
    assert src["optimal_pct"] == 10.0
    assert src["action"] == "HOLD"
    assert out["optimal_pct"] == 5.0
    assert out["recommended_usd"] == pytest.approx(500.0)
    assert out["delta_usd"] == pytest.approx(300.0)
    # 2.0 < 5.0 * 0.6 → ADD
    assert out["action"] == "ADD"
    assert out["corr_haircut"] == 0.5
