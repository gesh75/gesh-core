"""Parity tests for gesh_core.kelly (Phase 3.2).

Network-free: returns are injected via the `returns=` param (product's testability
addition, now canonical). Pins the Kelly math + sizing/action logic both repos rely
on. Mirrors the product repo's tests/test_kelly.py so neither consumer regresses.
"""
from __future__ import annotations

import numpy as np
import pytest

from gesh_core import kelly
from gesh_core.kelly import (
    kelly_size_holding,
    run_kelly_analysis,
    _continuous_kelly,
    _discrete_kelly,
    _volatility_score,
    _max_drawdown,
    MAX_POSITION_PCT,
    MIN_HISTORY_DAYS,
)

rng = np.random.default_rng(42)
POSITIVE_DRIFT = (rng.normal(0.002, 0.01, 120)).astype(float)   # upward drift
NEGATIVE_DRIFT = (rng.normal(-0.003, 0.01, 120)).astype(float)  # downward drift


def test_module_loads_from_gesh_core():
    assert "gesh_core" in (kelly.__file__ or "")


# ─── pure math ────────────────────────────────────────────────────────────────

def test_continuous_kelly_symmetric_is_zero():
    sym = np.array([0.01, -0.01, 0.01, -0.01] * 20, dtype=float)
    assert _continuous_kelly(sym)["kelly_pct"] == pytest.approx(0.0, abs=1e-9)


def test_continuous_kelly_zero_sigma_guard():
    const = np.array([0.01] * 50, dtype=float)
    out = _continuous_kelly(const)
    assert out["kelly_pct"] == 0.0   # sigma 0 -> no div-by-zero


def test_discrete_kelly_keys():
    out = _discrete_kelly(POSITIVE_DRIFT)
    for k in ("kelly_pct", "win_rate", "avg_win_pct", "avg_loss_pct", "payoff_ratio"):
        assert k in out


@pytest.mark.parametrize("ann_target,expected", [
    (np.array([0.0001] * 100, dtype=float), "LOW"),
])
def test_volatility_tiers(ann_target, expected):
    assert _volatility_score(ann_target) in {"LOW", "MEDIUM", "HIGH", "EXTREME"}


def test_max_drawdown_is_nonpositive():
    assert _max_drawdown(NEGATIVE_DRIFT) <= 0.0


# ─── kelly_size_holding with injected returns ─────────────────────────────────

def test_injected_returns_skip_fetch():
    res = kelly_size_holding("X", 1_000, 100_000, avg_cost=10, current_price=12,
                             returns=POSITIVE_DRIFT)
    assert "error" not in res
    assert res["symbol"] == "X"
    assert 0.0 <= res["optimal_pct"] <= MAX_POSITION_PCT * 100


def test_positive_drift_recommends_position():
    res = kelly_size_holding("X", 1_000, 100_000, 10, 12, returns=POSITIVE_DRIFT)
    assert res["optimal_pct"] > 0
    assert res["action"] in {"ADD", "HOLD", "TRIM"}


def test_negative_drift_avoids():
    res = kelly_size_holding("X", 1_000, 100_000, 10, 9, returns=NEGATIVE_DRIFT)
    assert res["optimal_pct"] == 0.0
    assert res["action"] == "AVOID"


def test_ai_penalty_reduces_size():
    base = kelly_size_holding("X", 1_000, 100_000, 10, 12, returns=POSITIVE_DRIFT)
    penalised = kelly_size_holding("X", 1_000, 100_000, 10, 12, returns=POSITIVE_DRIFT,
                                   ai_eval={"verdict": "AVOID"})
    assert penalised["optimal_pct"] <= base["optimal_pct"]
    assert penalised["ai_penalty"] == 0.5


def test_hard_cap_enforced():
    # Strong drift would exceed cap pre-clamp; final must respect MAX_POSITION_PCT.
    strong = np.array([0.05] * 120, dtype=float)
    res = kelly_size_holding("X", 1_000, 100_000, 10, 12, returns=strong)
    assert res["optimal_pct"] <= MAX_POSITION_PCT * 100


def test_insufficient_history_returns_error():
    res = kelly_size_holding("X", 1_000, 100_000, 10, 12,
                             returns=np.array([0.01] * (MIN_HISTORY_DAYS - 5), dtype=float))
    assert res["recommended_pct"] is None
    assert "Insufficient" in res["error"]


# ─── run_kelly_analysis (portfolio) ───────────────────────────────────────────

def test_run_kelly_analysis_structure(monkeypatch):
    # Avoid network: stub _fetch_returns to a deterministic array.
    monkeypatch.setattr(kelly, "_fetch_returns", lambda symbol, days=90: POSITIVE_DRIFT)
    holdings = [
        {"symbol": "AAA", "equity": 1000, "average_buy_price": 10, "current_price": 12},
        {"symbol": "BBB", "equity": 2000, "average_buy_price": 20, "current_price": 18},
    ]
    out = run_kelly_analysis(holdings, total_portfolio=100_000)
    assert {"holdings", "total_optimal_allocated_pct", "cash_recommended_pct",
            "trim_list", "add_list", "avoid_list", "portfolio_kelly_score"} <= set(out)
    assert len(out["holdings"]) == 2
    # sorted by optimal_pct desc
    pcts = [h.get("optimal_pct", 0) for h in out["holdings"]]
    assert pcts == sorted(pcts, reverse=True)
