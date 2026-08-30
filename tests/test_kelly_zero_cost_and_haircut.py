"""Leftover Kelly edges: zero/negative cost basis and haircut fail-open.

``pnl_pct`` divides by avg_cost; a host passing 0 or a negative basis must not
emit Inf/NaN into the dashboard JSON. Correlation haircuts must never UP-size
a name when a peer series is missing (fail-open at 1.0).
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from gesh_core import kelly
from gesh_core.kelly import kelly_size_holding

rng = np.random.default_rng(42)
POSITIVE_DRIFT = rng.normal(0.002, 0.01, 120).astype(float)


def test_zero_avg_cost_reports_zero_pnl_not_inf():
    res = kelly_size_holding(
        "X", 1_000, 100_000, avg_cost=0.0, current_price=12.0, returns=POSITIVE_DRIFT
    )
    assert res["pnl_pct"] == 0.0
    assert math.isfinite(res["pnl_pct"])
    assert "error" not in res


def test_negative_avg_cost_reports_zero_pnl_not_a_fabricated_gain():
    res = kelly_size_holding(
        "X", 1_000, 100_000, avg_cost=-10.0, current_price=12.0, returns=POSITIVE_DRIFT
    )
    assert res["pnl_pct"] == 0.0
    assert math.isfinite(res["pnl_pct"])


def test_haircut_fail_open_when_peer_returns_missing():
    hc = kelly._correlation_haircuts(
        ["A", "B"], {"A": POSITIVE_DRIFT, "B": None}, threshold=0.7
    )
    assert hc == {"A": pytest.approx(1.0), "B": pytest.approx(1.0)}


def test_haircut_fail_open_when_only_one_usable_series():
    hc = kelly._correlation_haircuts(["A"], {"A": POSITIVE_DRIFT}, threshold=0.7)
    assert hc == {"A": pytest.approx(1.0)}
