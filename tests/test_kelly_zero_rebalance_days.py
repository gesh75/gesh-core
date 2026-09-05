"""KELLY_REBALANCE_DAYS <= 0 must not divide-by-zero inside the cost haircut.

A zero/negative amortization horizon is treated as frictionless (drag 0) so a
mis-set env cannot crash every kelly_size_holding call in the daily chain.
"""
from __future__ import annotations

import numpy as np
import pytest

from gesh_core import kelly
from gesh_core.kelly import kelly_size_holding

POSITIVE_DRIFT = np.full(80, 0.002, dtype=float) + np.random.default_rng(0).normal(0, 0.01, 80)


@pytest.mark.parametrize("days", ["0", "-5"])
def test_non_positive_rebalance_days_is_zero_drag(monkeypatch, days):
    monkeypatch.setenv("KELLY_REBALANCE_DAYS", days)
    monkeypatch.setenv("KELLY_COST_BPS", "400")
    assert kelly._cost_drag_daily() == 0.0

    res = kelly_size_holding("X", 1_000, 100_000, 10, 12, returns=POSITIVE_DRIFT)
    assert "error" not in res
    assert res["cost_drag_daily"] == 0.0
    assert res["optimal_pct"] >= 0.0
