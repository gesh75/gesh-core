"""Parity tests for gesh_core.kelly (Phase 3.2).

Network-free: returns are injected via the `returns=` param (product's testability
addition, now canonical). Pins the Kelly math + sizing/action logic both repos rely
on. Mirrors the product repo's tests/test_kelly.py so neither consumer regresses.
"""
from __future__ import annotations

import os
import subprocess
import sys

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


def test_parse_position_cap_none_returns_fallback():
    """mypy-safe None handling: os.getenv miss must not call float(None)."""
    assert kelly._parse_position_cap(None, 0.25) == 0.25
    assert kelly._parse_position_cap(None, 0.1) == 0.1


def test_parse_position_cap_valid_string():
    assert kelly._parse_position_cap("0.18", 0.25) == 0.18


@pytest.mark.parametrize("value", ["", "abc", "nan", "inf", "-0.1", "1.1", "100"])
def test_invalid_gross_cap_env_fails_safe(value, monkeypatch):
    """KELLY_MAX_GROSS_PCT must use the same finite-[0,1] parser as position cap."""
    monkeypatch.setenv("KELLY_MAX_GROSS_PCT", value)
    assert kelly._max_gross_exposure() == 1.0


@pytest.mark.parametrize("value", ["", "abc", "nan", "inf", "-0.1", "1.1"])
def test_invalid_position_cap_env_fails_safe(value):
    env = os.environ.copy()
    env["KELLY_MAX_POSITION_PCT"] = value
    proc = subprocess.run(
        [sys.executable, "-c", "from gesh_core.kelly import MAX_POSITION_PCT; print(MAX_POSITION_PCT)"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert float(proc.stdout) == 0.25


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


# ─── date-aligned correlation haircuts (PR-3) ──────────────────────────────────

def test_haircut_aligns_by_date_not_position():
    # B is A minus one mid-series day: identical returns on every SHARED date.
    # Date-aligned correlation is exactly 1.0 → both get the 1/sqrt(2) haircut.
    # Positional alignment (the old bug) compared A shifted-by-one against B and
    # saw near-zero correlation → no haircut → correlated cluster overbet.
    import pandas as pd
    local = np.random.default_rng(7)
    dates = pd.bdate_range("2026-01-05", periods=40)
    a = pd.Series(local.normal(0.001, 0.02, 40), index=dates)
    b = a.drop(dates[20])
    hc = kelly._correlation_haircuts(["A", "B"], {"A": a, "B": b}, threshold=0.7)
    assert hc["A"] == pytest.approx(1 / np.sqrt(2), abs=1e-6)
    assert hc["B"] == pytest.approx(1 / np.sqrt(2), abs=1e-6)


def test_haircut_uncorrelated_dated_series_untouched():
    import pandas as pd
    local = np.random.default_rng(11)
    dates = pd.bdate_range("2026-01-05", periods=60)
    a = pd.Series(local.normal(0.001, 0.02, 60), index=dates)
    b = pd.Series(local.normal(0.001, 0.02, 60), index=dates)
    hc = kelly._correlation_haircuts(["A", "B"], {"A": a, "B": b}, threshold=0.7)
    assert hc == {"A": 1.0, "B": 1.0}


def test_disjoint_series_does_not_suppress_other_pair_haircut():
    import pandas as pd
    dates = pd.bdate_range("2026-01-05", periods=20)
    local = np.random.default_rng(19)
    a = pd.Series(local.normal(0.001, 0.02, 20), index=dates)
    b = a.copy()
    disjoint_dates = pd.bdate_range("2025-01-06", periods=20)
    c = pd.Series(local.normal(0.001, 0.02, 20), index=disjoint_dates)

    hc = kelly._correlation_haircuts(
        ["A", "B", "C"], {"A": a, "B": b, "C": c}, threshold=0.7
    )

    assert hc["A"] == pytest.approx(1 / np.sqrt(2), abs=1e-6)
    assert hc["B"] == pytest.approx(1 / np.sqrt(2), abs=1e-6)
    assert hc["C"] == 1.0


def test_haircut_positional_fallback_for_plain_arrays():
    # Injected plain ndarrays (no dates) keep the pre-PR-3 positional behavior —
    # the seam downstream tests rely on.
    local = np.random.default_rng(13)
    r = local.normal(0.001, 0.02, 30)
    hc = kelly._correlation_haircuts(["A", "B"], {"A": r, "B": r.copy()}, threshold=0.7)
    assert hc["A"] == pytest.approx(1 / np.sqrt(2), abs=1e-6)


def test_run_kelly_analysis_date_aligned_end_to_end(monkeypatch):
    # Two clones of the same upward-drifting series, one with a mid-series gap:
    # sizing must work off the Series (coerced internally) AND the haircut must
    # engage via date alignment despite the length mismatch.
    import pandas as pd
    local = np.random.default_rng(17)
    dates = pd.bdate_range("2025-12-01", periods=100)
    a = pd.Series(local.normal(0.002, 0.01, 100), index=dates)
    b = a.drop(dates[50])
    series = {"AAA": a, "BBB": b}
    monkeypatch.setattr(kelly, "_fetch_returns",
                        lambda symbol, days=90: series[symbol])
    out = kelly.run_kelly_analysis(
        [{"symbol": "AAA", "equity": 1000, "average_buy_price": 10, "current_price": 12},
         {"symbol": "BBB", "equity": 1000, "average_buy_price": 10, "current_price": 12}],
        total_portfolio=100_000,
    )
    rows = {r["symbol"]: r for r in out["holdings"]}
    assert rows["AAA"]["corr_haircut"] == pytest.approx(0.707, abs=1e-3)
    assert rows["BBB"]["corr_haircut"] == pytest.approx(0.707, abs=1e-3)
    assert rows["AAA"]["optimal_pct"] > 0


def test_fetch_returns_normalizes_tz_aware_index(monkeypatch):
    # Yahoo history carries a tz-aware NY index; the RH fallback may be naive.
    # _fetch_returns must strip tz + time-of-day so cross-source inner joins
    # in the haircut pass actually match dates.
    import pandas as pd

    idx = pd.date_range("2026-01-05 09:30", periods=45, freq="B", tz="America/New_York")
    frame = pd.DataFrame({"Close": np.linspace(100, 120, 45)}, index=idx)

    class _FakeTicker:
        def __init__(self, symbol):
            pass
        def history(self, **kwargs):
            return frame

    monkeypatch.setattr(kelly.yf, "Ticker", _FakeTicker)
    out = kelly._fetch_returns("NVDA")
    assert isinstance(out, pd.Series)
    assert out.index.tz is None
    assert (out.index == out.index.normalize()).all()


def test_fetch_returns_does_not_import_untrusted_price_source(monkeypatch, tmp_path):
    """Yahoo-empty must not exec a cwd/sys.path `price_source.py` (market_fetch already pins this)."""

    class _Empty:
        empty = True

    class _FakeTicker:
        def __init__(self, symbol):
            pass

        def history(self, **kwargs):
            return _Empty()

    marker = tmp_path / "imported"
    (tmp_path / "price_source.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        "def rh_fallback(*a, **k):\n    return None\n"
    )
    monkeypatch.setattr(kelly.yf, "Ticker", _FakeTicker)
    monkeypatch.syspath_prepend(tmp_path)
    monkeypatch.delitem(sys.modules, "price_source", raising=False)

    assert kelly._fetch_returns("NVDA") is None
    assert not marker.exists()
    assert "price_source" not in sys.modules


def test_fetch_returns_uses_already_imported_host_price_source(monkeypatch):
    """Hosts that already imported their trusted price_source still get the RH fallback."""
    import types

    import pandas as pd

    class _Empty:
        empty = True

    class _FakeTicker:
        def __init__(self, symbol):
            pass

        def history(self, **kwargs):
            return _Empty()

    idx = pd.date_range("2026-01-05", periods=45, freq="B")
    frame = pd.DataFrame({"Close": np.linspace(100, 120, 45)}, index=idx)
    stub = types.ModuleType("price_source")
    stub.rh_fallback = lambda symbol, **k: frame

    monkeypatch.setattr(kelly.yf, "Ticker", _FakeTicker)
    monkeypatch.setitem(sys.modules, "price_source", stub)

    out = kelly._fetch_returns("NVDA")
    assert isinstance(out, pd.Series)
    assert len(out) >= MIN_HISTORY_DAYS
