"""Parity tests for gesh_core.ecg (Phase 3.2).

The product version is canonical. These pin both the pure helpers (also covered
by the engine's test_gesh_core_candidates through the shim) AND the bug fix that
made it canonical: compute_ecg derives loss streaks from equity CHANGES, so an
underwater-but-flat holding is NOT falsely SUSPENDED.
"""
from __future__ import annotations

import math

import pytest

from gesh_core import ecg


def test_module_loads_from_gesh_core():
    assert "gesh_core" in (ecg.__file__ or "")


# ─── pure helpers ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("equities,expected", [
    ([100, 200, 150], -25.0),   # peak-then-crash from running peak
    ([100, 150, 200], 0.0),     # still at peak
    ([100], 0.0),               # too few
    ([], 0.0),
    ([0, 0, 0], 0.0),           # non-positive peak guard
])
def test_drawdown_from_running_peak(equities, expected):
    assert ecg._compute_drawdown_from_peak(equities) == pytest.approx(expected)


def test_loss_streak_counts_trailing_negatives():
    assert ecg._loss_streak([1.0, -1.0, -1.0, -1.0]) == 3
    assert ecg._loss_streak([-1.0, -1.0, 1.0]) == 0
    assert ecg._loss_streak([]) == 0


@pytest.mark.parametrize("dd,streak,expected", [
    (-20.0, 0, "SUSPENDED"),
    (-19.9, 0, "COOLING"),
    (-8.0, 0, "COOLING"),
    (-7.99, 0, "HEALTHY"),
    (0.0, 6, "SUSPENDED"),
    (0.0, 3, "COOLING"),
    (0.0, 2, "HEALTHY"),
])
def test_classify_thresholds(dd, streak, expected):
    assert ecg._classify(dd, streak) == expected


# ─── compute_ecg: the canonical bug fix ───────────────────────────────────────

def _hist(equities):
    # history_fn returns NEWEST-FIRST rows; percent_change is intentionally a
    # large negative LEVEL (gain/loss vs cost) to prove the streak does NOT use it.
    rows = [{"equity": e, "percent_change": -99.0, "current_price": e} for e in equities]
    return list(reversed(rows))  # newest-first


def test_underwater_but_rising_is_not_suspended():
    # Equity rising every snapshot -> 0 loss streak, despite percent_change=-99.
    holdings = [{"symbol": "AAA", "equity": 130}]
    out = ecg.compute_ecg(holdings, lambda s: _hist([100, 110, 120, 130]))
    st = out["states"][0]
    assert st["loss_streak"] == 0          # NOT driven by percent_change
    assert st["state"] == "HEALTHY"
    assert "severe drawdown" not in st["message"]


def test_real_equity_crash_trips_suspended():
    holdings = [{"symbol": "BBB", "equity": 70}]
    out = ecg.compute_ecg(holdings, lambda s: _hist([100, 200, 70]))
    st = out["states"][0]
    assert st["state"] == "SUSPENDED"       # -65% from peak
    assert "drawdown" in st["message"]


@pytest.mark.parametrize("bad_equity", [float("nan"), float("inf"), float("-inf"), None, "bad"])
def test_malformed_equity_history_fails_closed(bad_equity):
    holdings = [{"symbol": "BAD-DATA", "equity": 70}]
    out = ecg.compute_ecg(holdings, lambda s: _hist([100, bad_equity, 70]))
    st = out["states"][0]

    assert st["state"] == "SUSPENDED"
    assert out["portfolio_gate"] == "SUSPENDED"
    assert math.isfinite(st["drawdown_pct"])
    assert st["equity_history"] == []
    assert "invalid" in st["message"]


def test_single_malformed_snapshot_fails_closed():
    out = ecg.compute_ecg(
        [{"symbol": "BAD-DATA", "equity": 0}],
        lambda s: _hist([float("nan")]),
    )

    assert out["states"][0]["state"] == "SUSPENDED"


def test_consecutive_equity_declines_build_streak():
    holdings = [{"symbol": "CCC", "equity": 94}]
    # 6 consecutive small declines -> streak >= 6 -> SUSPENDED via streak (not dd)
    out = ecg.compute_ecg(holdings, lambda s: _hist([100, 99, 98, 97, 96, 95, 94]))
    st = out["states"][0]
    assert st["loss_streak"] >= 6
    assert st["state"] == "SUSPENDED"
    assert "consecutive losing snapshots" in st["message"]


def test_insufficient_history_is_healthy():
    out = ecg.compute_ecg([{"symbol": "DDD", "equity": 50}], lambda s: _hist([50]))
    st = out["states"][0]
    assert st["state"] == "HEALTHY"
    assert "Insufficient history" in st["message"]


def test_portfolio_gate_worst_state_wins():
    holdings = [{"symbol": "OK", "equity": 110}, {"symbol": "BAD", "equity": 70}]
    def hist(sym):
        return _hist([100, 110]) if sym == "OK" else _hist([100, 200, 70])
    out = ecg.compute_ecg(holdings, hist)
    assert out["portfolio_gate"] == "SUSPENDED"
    assert "SUSPENDED" in out["portfolio_message"]


def test_equity_history_capped_at_30():
    eqs = list(range(1, 50))  # 49 points
    out = ecg.compute_ecg([{"symbol": "E", "equity": 49}], lambda s: _hist(eqs))
    assert len(out["states"][0]["equity_history"]) == 30
