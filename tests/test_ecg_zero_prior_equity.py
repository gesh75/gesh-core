"""A zero prior equity must not divide-by-zero when building the loss streak.

``chg_list`` uses ``eq_list[i] / eq_list[i-1]`` only when the prior point is
truthy. A 0 → N recovery (or a $0 paper mark) must stay finite so the
portfolio gate cannot fail open on NaN comparisons.
"""
from __future__ import annotations

import math

from gesh_core import ecg


def _hist(equities: list[float]) -> list[dict]:
    rows = [{"equity": e, "percent_change": -99.0, "current_price": e} for e in equities]
    return list(reversed(rows))


def test_zero_then_positive_equity_does_not_crash_or_suspend():
    out = ecg.compute_ecg(
        [{"symbol": "Z", "equity": 100}],
        lambda s: _hist([0.0, 100.0]),
    )
    st = out["states"][0]
    assert math.isfinite(st["drawdown_pct"])
    assert st["loss_streak"] == 0
    assert st["state"] == "HEALTHY"
    assert out["portfolio_gate"] == "HEALTHY"


def test_positive_then_zero_equity_is_a_full_drawdown():
    out = ecg.compute_ecg(
        [{"symbol": "Z", "equity": 0}],
        lambda s: _hist([100.0, 0.0]),
    )
    st = out["states"][0]
    assert st["state"] == "SUSPENDED"
    assert st["drawdown_pct"] == -100.0
    assert math.isfinite(st["drawdown_pct"])
