"""Practitioner-review methodology pins that open DCF PRs do not cover.

Complements PR #35 (valuation guards / `_avg_ratio`) and PR #36 (statement
alignment). These lock:

  - Blume-adjusted beta fragility (MPC +84% → -1% at market beta)
  - `_growth_path` CAGR cap and "not enough history" fallback
  - refuse a non-positive model price rather than publish it
  - named error when `DCFInputs.available` lies about completeness
  - exact financial-sector exclusion currently on main
"""

from __future__ import annotations

import pytest

from gesh_core.dcf.fair_value import (
    BETA_FRAGILE_SWING_PCT,
    DEFAULT_BETA,
    PROJECTION_YEARS,
    _growth_path,
    compute_fair_value,
    value_with_assumptions,
)
from gesh_core.dcf.inputs import DCFInputs


def _ok_inputs(**overrides: object) -> DCFInputs:
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


def _patch_fetch(
    monkeypatch: pytest.MonkeyPatch,
    data: DCFInputs,
    profile: tuple[float, bool, str | None] = (1.1, True, "Technology"),
) -> None:
    monkeypatch.setattr("gesh_core.dcf.fair_value.fetch_dcf_inputs", lambda symbol: data)
    monkeypatch.setattr("gesh_core.dcf.fair_value._fetch_profile", lambda symbol: profile)


# ─── growth path ──────────────────────────────────────────────────────────────


def test_growth_path_caps_extrapolated_cagr_at_sixty_percent():
    # 100 → 400 in one year is a 300% CAGR; the path must not start there.
    path = _growth_path((100.0, 400.0), terminal=0.03, years=5)
    assert path[0] == pytest.approx(0.60)
    assert path[-1] == pytest.approx(0.03)
    assert path == sorted(path, reverse=True)


def test_growth_path_floors_at_terminal_when_history_is_shrinking():
    path = _growth_path((200.0, 100.0), terminal=0.03, years=5)
    assert path == pytest.approx([0.03] * 5)


def test_growth_path_falls_back_to_terminal_without_usable_history():
    assert _growth_path((100.0,), terminal=0.03, years=5) == [0.03] * 5
    assert _growth_path((0.0, 100.0), terminal=0.03, years=5) == [0.03] * 5
    assert _growth_path((-10.0, 100.0), terminal=0.025, years=3) == [0.025] * 3


# ─── beta fragility ───────────────────────────────────────────────────────────


def test_compute_fair_value_flags_fragile_low_regression_beta(monkeypatch):
    """MPC-class case: a ~0.5 2y beta must mark the headline as fragile."""
    _patch_fetch(monkeypatch, _ok_inputs(symbol="MPC"), profile=(0.508, True, "Energy"))
    result = compute_fair_value("MPC")
    assert "error" not in result
    sens = result["beta_sensitivity"]
    assert sens is not None
    assert sens["fair_value_at_market_beta"] > 0
    assert sens["swing_pct"] > BETA_FRAGILE_SWING_PCT
    assert sens["fragile"] is True
    assert result["inputs_fetched"]["beta_is_blume_adjusted"] is True
    assert result["inputs_fetched"]["beta"] != pytest.approx(0.508)


def test_compute_fair_value_not_fragile_near_market_beta(monkeypatch):
    _patch_fetch(monkeypatch, _ok_inputs(), profile=(1.05, True, "Technology"))
    result = compute_fair_value("AMD")
    assert "error" not in result
    sens = result["beta_sensitivity"]
    assert sens is not None
    assert sens["fragile"] is False
    assert sens["swing_pct"] <= BETA_FRAGILE_SWING_PCT


# ─── refusal / fail-closed ────────────────────────────────────────────────────


def test_compute_fair_value_refuses_non_positive_model_price(monkeypatch):
    _patch_fetch(monkeypatch, _ok_inputs(symbol="RKLB"))

    def _negative_price(*_a, **_k):
        return {
            "fair_value_per_share": -10.67,
            "enterprise_value_musd": -100.0,
            "equity_value_musd": -100.0,
            "terminal_pct_of_ev": 80.0,
            "wacc": 0.08,
        }

    monkeypatch.setattr("gesh_core.dcf.fair_value.value_with_assumptions", _negative_price)
    result = compute_fair_value("RKLB")
    assert result["fetched"] is True
    assert "error" in result
    assert "non-positive" in result["error"]
    assert "fair_value_per_share" not in result


def test_compute_fair_value_names_desynced_available_flag(monkeypatch):
    """`available` can be True while tax/shares/net_debt are None — refuse, no TypeError."""
    lying = _ok_inputs(tax_rate=None, shares_outstanding=None, net_debt=None)
    assert lying.available is True
    _patch_fetch(monkeypatch, lying)
    result = compute_fair_value("AMD")
    assert result["fetched"] is True
    assert "out of sync" in result["error"]
    assert "fair_value_per_share" not in result


@pytest.mark.parametrize("sector", ["Financial Services", "Financials"])
def test_compute_fair_value_excludes_named_financial_sectors(monkeypatch, sector):
    _patch_fetch(monkeypatch, _ok_inputs(symbol="JPM"), profile=(1.0, True, sector))
    result = compute_fair_value("JPM")
    assert "error" in result
    assert "sector" in result["error"]
    assert sector in result["error"]


def test_compute_fair_value_does_not_exclude_adjacent_sectors(monkeypatch):
    _patch_fetch(monkeypatch, _ok_inputs(symbol="V"), profile=(1.0, True, "Financial Technology"))
    result = compute_fair_value("V")
    assert "error" not in result
    assert result["fair_value_per_share"] > 0


def test_value_with_assumptions_is_deterministic():
    kwargs = dict(
        data=_ok_inputs(),
        beta=DEFAULT_BETA,
        growth=[0.08, 0.07, 0.06, 0.05, 0.04],
        margins=[0.30] * PROJECTION_YEARS,
        capex_pct=0.05,
        nwc_pct=0.20,
    )
    first = value_with_assumptions(**kwargs)
    second = value_with_assumptions(**kwargs)
    assert first == second
    assert first["fair_value_per_share"] > 0
