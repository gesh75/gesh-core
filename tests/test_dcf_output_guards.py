"""Fail-closed DCF output guards that existing characterization tests skip.

``tests/test_dcf.py`` covers input-side refusals (sector, margin, NWC, capex,
zero revenue). These pin the *output* contract: refuse a non-positive price,
flag a fragile beta swing, and fail named when ``available`` drifts from
populated scalars.
"""

from __future__ import annotations

from typing import Any

import pytest

from gesh_core.dcf.fair_value import (
    BETA_FRAGILE_SWING_PCT,
    DEFAULT_BETA,
    blume_beta,
    compute_fair_value,
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


def _core(fv: float) -> dict[str, Any]:
    return {
        "fair_value_per_share": fv,
        "enterprise_value_musd": 1.0,
        "equity_value_musd": 1.0,
        "terminal_pct_of_ev": 50.0,
        "wacc": 0.10,
    }


def _patch_fetch(
    monkeypatch: pytest.MonkeyPatch,
    data: DCFInputs,
    profile: tuple[float, bool, str] = (1.1, True, "Technology"),
) -> None:
    monkeypatch.setattr("gesh_core.dcf.fair_value.fetch_dcf_inputs", lambda symbol: data)
    monkeypatch.setattr("gesh_core.dcf.fair_value._fetch_profile", lambda symbol: profile)


@pytest.mark.parametrize("fv", [0.0, -10.0, -0.01])
def test_compute_fair_value_refuses_non_positive_model_output(
    monkeypatch: pytest.MonkeyPatch, fv: float
) -> None:
    _patch_fetch(monkeypatch, _ok_inputs())
    monkeypatch.setattr(
        "gesh_core.dcf.fair_value.value_with_assumptions",
        lambda *args, **kwargs: _core(fv),
    )
    result = compute_fair_value("AMD")
    assert result["fetched"] is True
    assert "error" in result
    assert "non-positive" in result["error"]
    assert "fair_value_per_share" not in result


def test_available_true_but_scalar_none_is_named_sync_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``available`` does not inspect tax/shares/net_debt — the public API must."""
    data = _ok_inputs(tax_rate=None)
    assert data.available is True
    _patch_fetch(monkeypatch, data)
    result = compute_fair_value("AMD")
    assert result["fetched"] is True
    assert "out of sync" in result["error"]
    assert "fair_value_per_share" not in result


def test_beta_sensitivity_marks_fragile_when_swing_exceeds_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_beta = 0.5
    blume = blume_beta(raw_beta)
    assert blume != pytest.approx(1.0)

    def _value(_data: Any, beta: float, **_kwargs: Any) -> dict[str, Any]:
        # Headline at the Blume beta; market-beta rerun is 50% lower → fragile.
        return _core(100.0 if beta != 1.0 else 50.0)

    _patch_fetch(monkeypatch, _ok_inputs(), profile=(raw_beta, True, "Energy"))
    monkeypatch.setattr("gesh_core.dcf.fair_value.value_with_assumptions", _value)
    result = compute_fair_value("AMD")
    assert "error" not in result
    sens = result["beta_sensitivity"]
    assert sens["fair_value_at_market_beta"] == pytest.approx(50.0)
    assert sens["swing_pct"] == pytest.approx(50.0)
    assert sens["swing_pct"] > BETA_FRAGILE_SWING_PCT
    assert sens["fragile"] is True


def test_beta_sensitivity_not_fragile_under_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    def _value(_data: Any, beta: float, **_kwargs: Any) -> dict[str, Any]:
        return _core(100.0 if beta != 1.0 else 90.0)

    _patch_fetch(monkeypatch, _ok_inputs(), profile=(0.8, True, "Technology"))
    monkeypatch.setattr("gesh_core.dcf.fair_value.value_with_assumptions", _value)
    result = compute_fair_value("AMD")
    sens = result["beta_sensitivity"]
    assert sens["swing_pct"] == pytest.approx(10.0)
    assert sens["swing_pct"] < BETA_FRAGILE_SWING_PCT
    assert sens["fragile"] is False


def test_no_beta_sensitivity_when_profile_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fetch(monkeypatch, _ok_inputs(), profile=(DEFAULT_BETA, False, "Technology"))
    monkeypatch.setattr(
        "gesh_core.dcf.fair_value.value_with_assumptions",
        lambda *args, **kwargs: _core(80.0),
    )
    result = compute_fair_value("AMD")
    assert result["beta_sensitivity"] is None
    assert result["fair_value_per_share"] == pytest.approx(80.0)
