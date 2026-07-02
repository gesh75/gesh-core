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
    MAX_POSITION_PCT,
    MIN_HISTORY_DAYS,
    _continuous_kelly,
    _discrete_kelly,
    _max_drawdown,
    _volatility_score,
    kelly_size_holding,
    run_kelly_analysis,
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


# ─── H2: portfolio reconciliation (gross cap + correlation haircut) ────────────


def _holding(sym: str) -> dict:
    return {"symbol": sym, "equity": 1000, "average_buy_price": 10, "current_price": 12}


def test_under_cap_uncorrelated_is_unchanged(monkeypatch):
    """Backward-compat guard: a small, uncorrelated book is not rescaled."""
    # Two INDEPENDENT positive-drift series → near-zero correlation.
    a = rng.normal(0.002, 0.01, 120).astype(float)
    b = rng.normal(0.002, 0.01, 120).astype(float)
    series = {"AAA": a, "BBB": b}
    monkeypatch.setattr(kelly, "_fetch_returns",
                        lambda symbol, days=90: series[symbol])

    out = run_kelly_analysis([_holding("AAA"), _holding("BBB")], total_portfolio=100_000)

    assert out["gross_scale_factor"] == pytest.approx(1.0)
    assert out["rescaled"] is False
    for h in out["holdings"]:
        assert h["corr_haircut"] == pytest.approx(1.0)


def test_correlated_names_get_haircut(monkeypatch):
    """Two highly-correlated names must be sized strictly smaller than when
    the same names are uncorrelated (EXA: treat a correlated cluster as one theme)."""
    base = rng.normal(0.002, 0.01, 120).astype(float)

    # Correlated book: BBB ≈ AAA (corr ≈ 1.0)
    corr_series = {"AAA": base, "BBB": base + rng.normal(0, 0.0005, 120)}
    monkeypatch.setattr(kelly, "_fetch_returns", lambda symbol, days=90: corr_series[symbol])
    corr_out = run_kelly_analysis([_holding("AAA"), _holding("BBB")], total_portfolio=100_000)
    corr_pct = {h["symbol"]: h["optimal_pct"] for h in corr_out["holdings"]}

    # Uncorrelated book: independent draws
    indep_series = {"AAA": base, "BBB": rng.normal(0.002, 0.01, 120).astype(float)}
    monkeypatch.setattr(kelly, "_fetch_returns", lambda symbol, days=90: indep_series[symbol])
    indep_out = run_kelly_analysis([_holding("AAA"), _holding("BBB")], total_portfolio=100_000)
    indep_pct = {h["symbol"]: h["optimal_pct"] for h in indep_out["holdings"]}

    # AAA is identical in both books; only its correlation context changed.
    assert corr_pct["AAA"] < indep_pct["AAA"]
    # cluster of 2 → factor 1/sqrt(2) ≈ 0.707
    assert any(h["corr_haircut"] < 1.0 for h in corr_out["holdings"])


def test_gross_cap_rescales_overbet_book(monkeypatch):
    """When summed Kelly exceeds the gross cap, all positions scale to exactly the cap.

    The gross cap is read at call time from KELLY_MAX_GROSS_PCT, so no reload is
    needed. Four uncorrelated strong-drift names each hit the 25% single-name cap
    pre-rescale → ~100% gross, far above a 30% cap.
    """
    # Distinct per-symbol drift so names are NOT mutually correlated (avoid the
    # haircut muddying the gross-cap assertion), each strongly positive.
    drifts = {"AAA": 0.030, "BBB": 0.028, "CCC": 0.026, "DDD": 0.024}
    series = {s: (np.full(120, d, dtype=float) + rng.normal(0, 0.01, 120)).astype(float)
              for s, d in drifts.items()}
    monkeypatch.setattr(kelly, "_fetch_returns", lambda symbol, days=90: series[symbol])
    monkeypatch.setenv("KELLY_MAX_GROSS_PCT", "0.30")  # 30% gross cap, easily exceeded

    holdings = [_holding(s) for s in drifts]
    out = run_kelly_analysis(holdings, total_portfolio=100_000)

    assert out["rescaled"] is True
    assert out["gross_scale_factor"] < 1.0
    assert out["total_optimal_allocated_pct"] == pytest.approx(30.0, abs=0.3)


# ─── M1: transaction-cost haircut on mu ───────────────────────────────────────


def test_cost_haircut_shrinks_thin_edge(monkeypatch):
    """Subtracting costs from mu shrinks a thin-edge position (EXA: use mu_net).

    Same returns, only the cost assumption changes; a heavy cost must size the
    position strictly smaller than a zero-cost run.
    """
    thin = (np.full(150, 0.0009, dtype=float) + rng.normal(0, 0.003, 150)).astype(float)

    monkeypatch.setenv("KELLY_COST_BPS", "0")
    no_cost = kelly_size_holding("X", 1000, 100_000, 10, 12, returns=thin)["optimal_pct"]

    monkeypatch.setenv("KELLY_COST_BPS", "400")  # heavy round-trip cost
    monkeypatch.setenv("KELLY_REBALANCE_DAYS", "21")
    with_cost = kelly_size_holding("X", 1000, 100_000, 10, 12, returns=thin)["optimal_pct"]

    assert with_cost < no_cost


# ─── M2: serial-dependence (autocorrelation) shrinkage ────────────────────────


def test_positive_autocorrelation_shrinks_size(monkeypatch):
    """Positively autocorrelated returns are sized smaller than the SAME values
    shuffled (EXA: adjust effective sample size when serial dependence exists).

    Shuffling preserves mean/std and the order-independent discrete-Kelly stats,
    so the only thing that changes is lag-1 autocorrelation — isolating M2.
    """
    monkeypatch.setenv("KELLY_COST_BPS", "0")  # isolate from M1
    eps = np.random.default_rng(3).normal(0, 0.01, 400)
    ar = np.zeros(400)
    for i in range(1, 400):
        ar[i] = 0.6 * ar[i - 1] + eps[i]
    # Demean then add a thin, EXACT drift so μ is controlled — the raw AR process
    # wanders to a large realized mean that would cap both runs and hide the shrink.
    ar = (ar - ar.mean() + 0.0001).astype(float)  # thin drift, positive autocorr
    shuffled = ar.copy()
    np.random.default_rng(9).shuffle(shuffled)   # same values, autocorr destroyed

    ac_size = kelly_size_holding("X", 1000, 100_000, 10, 12, returns=ar)["optimal_pct"]
    iid_size = kelly_size_holding("X", 1000, 100_000, 10, 12, returns=shuffled)["optimal_pct"]

    assert ac_size < iid_size


def test_run_kelly_analysis_all_error_rows_score_is_zero(monkeypatch):
    # All symbols fail to fetch -> every row is an error row -> the positive-
    # half_kelly list is empty. Score must be 0.0, never NaN (breaks JSON).
    monkeypatch.setattr(kelly, "_fetch_returns", lambda *a, **k: None)
    out = run_kelly_analysis(
        [{"symbol": "AAA", "equity": 100.0}, {"symbol": "BBB", "equity": 200.0}],
        total_portfolio=1000.0,
    )
    score = out["portfolio_kelly_score"]
    assert score == 0.0
    assert not np.isnan(score)


def test_max_position_cap_read_at_call_time(monkeypatch):
    # Env change AFTER import must take effect (long-lived server processes).
    monkeypatch.setenv("KELLY_MAX_POSITION_PCT", "0.05")
    r = kelly_size_holding("NVDA", 0.0, 100_000.0, 10.0, 12.0, returns=POSITIVE_DRIFT)
    assert r["optimal_pct"] <= 5.0
    monkeypatch.delenv("KELLY_MAX_POSITION_PCT")
    r2 = kelly_size_holding("NVDA", 0.0, 100_000.0, 10.0, 12.0, returns=POSITIVE_DRIFT)
    assert r2["optimal_pct"] <= MAX_POSITION_PCT * 100
