"""Characterization tests for gesh_core.dcf (v0.7.0 landed with ZERO tests).

The valuation core is measurement-only (rule #47) and must stay network-free
here: fetch_dcf_inputs / _fetch_profile are monkeypatched. These pin the
practitioner-review guards (sector, margin, NWC, capex, non-positive price)
and the disclosed-assumption contract so a methodology change is reviewable.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from gesh_core.dcf.fair_value import (
    DEFAULT_BETA,
    MAX_CAPEX_PCT_OF_REVENUE,
    MAX_NWC_PCT_OF_REVENUE,
    MIN_EBITDA_MARGIN,
    PROJECTION_YEARS,
    _avg_ratio,
    _growth_path,
    blume_beta,
    compute_fair_value,
    value_with_assumptions,
)
from gesh_core.dcf.inputs import MIN_PERIODS, DCFInputs
from gesh_core.dcf.sensitivity import _base_assumptions


def _ok_inputs(**overrides: object) -> DCFInputs:
    """A profitable operator the percent-of-revenue method can actually value."""
    fields: dict[str, object] = {
        "symbol": "AMD",
        "years": (2023, 2024, 2025),
        "revenue": (20_000.0, 22_000.0, 25_000.0),
        "ebitda": (5_000.0, 6_000.0, 7_500.0),
        "capex": (1_000.0, 1_100.0, 1_250.0),
        "nwc": (4_000.0, 4_400.0, 5_000.0),
        "tax_rate": 0.15,
        "shares_outstanding": 1_600.0,
        "net_debt": -2_000.0,
    }
    fields.update(overrides)
    return DCFInputs(**fields)  # type: ignore[arg-type]


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, data: DCFInputs, profile=(1.1, True, "Technology")) -> None:
    monkeypatch.setattr("gesh_core.dcf.fair_value.fetch_dcf_inputs", lambda symbol: data)
    monkeypatch.setattr("gesh_core.dcf.fair_value._fetch_profile", lambda symbol: profile)


# ─── pure helpers ─────────────────────────────────────────────────────────────


def test_blume_beta_is_the_disclosed_shrinkage():
    assert blume_beta(1.0) == pytest.approx(1.0)
    assert blume_beta(0.508) == pytest.approx(0.67 * 0.508 + 0.33, abs=1e-4)


def test_avg_ratio_skips_zero_revenue_years():
    # Zero-revenue years are dropped, not treated as a 0% ratio and not a crash.
    assert _avg_ratio((10.0, 99.0, 20.0), (100.0, 0.0, 200.0)) == pytest.approx(0.10)


def test_avg_ratio_fails_closed_when_every_revenue_is_zero():
    with pytest.raises(ValueError, match="no positive-revenue"):
        _avg_ratio((1.0, 2.0, 3.0), (0.0, 0.0, 0.0))


def test_avg_ratio_fails_closed_when_every_revenue_is_negative():
    """`if r` is true for negatives; the contract is positive-revenue periods only."""
    with pytest.raises(ValueError, match="no positive-revenue"):
        _avg_ratio((1.0, 2.0), (-100.0, -200.0))


def test_growth_path_decays_cagr_toward_terminal():
    path = _growth_path((100.0, 110.0), terminal=0.03, years=5)
    assert len(path) == 5
    assert path[0] == pytest.approx(0.10, abs=1e-9)
    assert path[-1] == pytest.approx(0.03, abs=1e-9)


def test_growth_path_short_horizon_does_not_divide_by_zero():
    assert _growth_path((100.0, 110.0), terminal=0.03, years=1) == [0.03]
    assert _growth_path((100.0, 110.0), terminal=0.03, years=0) == []


def test_dcf_inputs_available_requires_aligned_min_periods():
    assert _ok_inputs().available is True
    short = _ok_inputs(years=(2024, 2025), revenue=(1.0, 2.0), ebitda=(1.0, 2.0),
                       capex=(0.1, 0.2), nwc=(0.2, 0.3))
    assert short.available is False
    assert MIN_PERIODS == 3


# ─── value_with_assumptions (pure, no network) ────────────────────────────────


def test_value_with_assumptions_returns_a_positive_price():
    out = value_with_assumptions(
        _ok_inputs(), 1.1,
        growth=[0.08, 0.07, 0.06, 0.05, 0.04],
        margins=[0.30] * PROJECTION_YEARS,
        capex_pct=0.05,
        nwc_pct=0.20,
    )
    assert "error" not in out
    assert out["fair_value_per_share"] > 0
    assert 0 < out["wacc"] < 0.25


def test_value_with_assumptions_refuses_terminal_at_or_above_wacc():
    out = value_with_assumptions(
        _ok_inputs(), 1.1,
        growth=[0.03] * PROJECTION_YEARS,
        margins=[0.30] * PROJECTION_YEARS,
        capex_pct=0.05,
        nwc_pct=0.20,
        terminal_growth=0.99,
    )
    assert "error" in out
    assert "WACC" in out["error"]


def test_value_with_assumptions_refuses_non_positive_revenue():
    data = _ok_inputs(revenue=(0.0, 22_000.0, 25_000.0))
    out = value_with_assumptions(
        data, 1.1,
        growth=[0.05] * PROJECTION_YEARS,
        margins=[0.30] * PROJECTION_YEARS,
        capex_pct=0.05,
        nwc_pct=0.20,
    )
    assert "error" in out
    assert "revenue" in out["error"]


# ─── compute_fair_value guards (fetch mocked) ─────────────────────────────────


def test_compute_fair_value_happy_path_discloses_capex_and_nwc(monkeypatch):
    _patch_fetch(monkeypatch, _ok_inputs())
    result = compute_fair_value("AMD")
    assert "error" not in result
    assert result["fair_value_per_share"] > 0
    assert "capex_pct" in result["assumptions"]
    assert "nwc_pct" in result["assumptions"]
    assert result["inputs_fetched"]["nwc"] == [4000, 4400, 5000]
    assert result["assumptions"]["nwc_pct"] == pytest.approx(
        _avg_ratio(_ok_inputs().nwc, _ok_inputs().revenue), abs=1e-4
    )


def test_compute_fair_value_excludes_financials_case_insensitively(monkeypatch):
    _patch_fetch(monkeypatch, _ok_inputs(symbol="JPM"), profile=(1.0, True, "financial services"))
    result = compute_fair_value("JPM")
    assert "error" in result
    assert "sector" in result["error"]


def test_compute_fair_value_refuses_pre_scale_margin(monkeypatch):
    data = _ok_inputs(ebitda=(100.0, 100.0, 100.0))  # 100/25000 = 0.4% << 5%
    _patch_fetch(monkeypatch, data)
    result = compute_fair_value("RKLB")
    assert "error" in result
    assert f"{MIN_EBITDA_MARGIN:.0%}" in result["error"] or "pre-scale" in result["error"]


def test_compute_fair_value_refuses_nwc_above_bound(monkeypatch):
    # 80% NWC of revenue, bound is 60%.
    data = _ok_inputs(nwc=(16_000.0, 17_600.0, 20_000.0))
    _patch_fetch(monkeypatch, data)
    result = compute_fair_value("IONQ")
    assert "error" in result
    assert f"{MAX_NWC_PCT_OF_REVENUE:.0%}" in result["error"]


def test_compute_fair_value_refuses_capex_above_bound(monkeypatch):
    data = _ok_inputs(capex=(8_000.0, 8_800.0, 10_000.0))  # 40% > 35%
    _patch_fetch(monkeypatch, data)
    result = compute_fair_value("MU")
    assert "error" in result
    assert f"{MAX_CAPEX_PCT_OF_REVENUE:.0%}" in result["error"]


def test_compute_fair_value_uses_default_beta_when_profile_missing(monkeypatch):
    _patch_fetch(monkeypatch, _ok_inputs(), profile=(DEFAULT_BETA, False, "Technology"))
    result = compute_fair_value("AMD")
    assert "error" not in result
    assert result["inputs_fetched"]["beta"] == DEFAULT_BETA
    assert result["inputs_fetched"]["beta_fetched"] is False
    assert result["beta_sensitivity"] is None


def test_base_assumptions_lockstep_with_compute_fair_value(monkeypatch):
    """sensitivity._base_assumptions must match compute_fair_value's derivation."""
    data = _ok_inputs()
    _patch_fetch(monkeypatch, data)
    result = compute_fair_value("AMD")
    base = _base_assumptions(data)
    assert result["assumptions"]["capex_pct"] == pytest.approx(base["capex_pct"], abs=1e-4)
    assert result["assumptions"]["nwc_pct"] == pytest.approx(base["nwc_pct"], abs=1e-4)
    assert result["assumptions"]["ebitda_margin_flat"] == pytest.approx(base["margins"][0], abs=1e-4)


def test_unavailable_inputs_return_error_not_a_guess(monkeypatch):
    missing = DCFInputs(symbol="ZZZ", error="empty statements")
    _patch_fetch(monkeypatch, missing)
    result = compute_fair_value("ZZZ")
    assert result["fetched"] is False
    assert "error" in result
    assert "fair_value_per_share" not in result


def test_compute_fair_value_fails_closed_on_all_zero_revenue(monkeypatch):
    """Public API must return a named error, not ZeroDivisionError / a guessed margin."""
    _patch_fetch(monkeypatch, _ok_inputs(revenue=(0.0, 0.0, 0.0)))
    result = compute_fair_value("ZZZ")
    assert "error" in result
    assert result["fetched"] is True
    assert "fair_value_per_share" not in result
    assert "revenue" in result["error"]


def test_compute_fair_value_fails_closed_on_mixed_zero_revenue(monkeypatch):
    """A single zero year is enough: the valuation core refuses, it does not skip."""
    _patch_fetch(monkeypatch, _ok_inputs(revenue=(0.0, 22_000.0, 25_000.0)))
    result = compute_fair_value("ZZZ")
    assert "error" in result
    assert result["fetched"] is True
    assert "fair_value_per_share" not in result
    assert "revenue" in result["error"]


# ─── package surface ──────────────────────────────────────────────────────────


def test_dcf_public_exports():
    from gesh_core import dcf
    assert set(dcf.__all__) >= {
        "DCFInputs", "compute_fair_value", "fetch_dcf_inputs",
        "run_sensitivity", "value_with_assumptions",
    }


@pytest.mark.skipif(sys.version_info < (3, 12), reason="package requires Python >= 3.12")
def test_every_non_vendor_module_imports():
    root = Path(__file__).resolve().parents[1] / "src" / "gesh_core"
    mods: set[str] = set()
    for path in root.rglob("*.py"):
        if "vendor" in path.parts:
            continue
        rel = path.relative_to(root.parent).with_suffix("").as_posix().replace("/", ".")
        if rel.endswith(".__init__"):
            rel = rel[: -len(".__init__")]
        if rel.endswith(".__main__"):
            continue
        mods.add(rel)
    assert "gesh_core.dcf" in mods
    assert "gesh_core.dcf.fair_value" in mods
    assert "gesh_core.ledger" in mods
    assert "gesh_core.sentiment_connector" in mods
    assert "gesh_core.market_fetch" in mods
    assert "gesh_core.trading.autopilot_core" in mods
    for name in sorted(mods):
        importlib.import_module(name)
