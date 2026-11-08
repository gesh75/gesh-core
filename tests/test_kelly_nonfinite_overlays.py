"""Call-time Kelly overlay knobs accept non-finite env values as parsed.

``_max_gross_exposure``, ``_corr_threshold``, and ``_cost_drag_daily`` only
catch TypeError/ValueError. ``inf`` / ``nan`` therefore load as IEEE values
rather than falling back to the defaults — a long-lived server that inherits
a bad launchd/.env value will either never bind the gross cap or NaN the
cost haircut. Pin the current fail-open so a later clamp is intentional.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from gesh_core import kelly


def test_max_gross_exposure_inf_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KELLY_MAX_GROSS_PCT", "inf")
    assert math.isinf(kelly._max_gross_exposure())


def test_max_gross_exposure_nan_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KELLY_MAX_GROSS_PCT", "nan")
    assert math.isnan(kelly._max_gross_exposure())


def test_corr_threshold_inf_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KELLY_CORR_THRESHOLD", "inf")
    assert math.isinf(kelly._corr_threshold())


def test_cost_drag_inf_days_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    # (bps / 1e4) / inf → 0.0; must not raise.
    monkeypatch.setenv("KELLY_COST_BPS", "10")
    monkeypatch.setenv("KELLY_REBALANCE_DAYS", "inf")
    assert kelly._cost_drag_daily() == 0.0


def test_cost_drag_inf_bps_is_inf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KELLY_COST_BPS", "inf")
    monkeypatch.setenv("KELLY_REBALANCE_DAYS", "21")
    assert math.isinf(kelly._cost_drag_daily())


def test_inf_gross_cap_does_not_rescale_an_overbet_book(monkeypatch: pytest.MonkeyPatch) -> None:
    """inf cap never binds (x > inf is False), so an overbet book stays unscaled."""
    rng = np.random.default_rng(0)
    drifts = {"AAA": 0.030, "BBB": 0.028, "CCC": 0.026, "DDD": 0.024}
    series = {
        s: (np.full(120, d, dtype=float) + rng.normal(0, 0.01, 120)).astype(float)
        for s, d in drifts.items()
    }
    monkeypatch.setattr(kelly, "_fetch_returns", lambda symbol, days=90: series[symbol])
    monkeypatch.setenv("KELLY_MAX_GROSS_PCT", "inf")

    holdings = [
        {"symbol": s, "equity": 1000, "average_buy_price": 10, "current_price": 12}
        for s in drifts
    ]
    out = kelly.run_kelly_analysis(holdings, total_portfolio=100_000)
    assert out["rescaled"] is False
    assert out["gross_scale_factor"] == pytest.approx(1.0)
    assert out["total_optimal_allocated_pct"] > 30.0
