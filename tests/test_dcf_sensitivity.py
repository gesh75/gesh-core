"""Characterization tests for DCF sensitivity (tornado + bear composite).

`run_sensitivity` fetches statements once, then re-values through
`value_with_assumptions`. It shipped with the v0.7/v0.8 DCF extraction and has
no in-repo coverage — a silent change to ranking, the bear composite, or the
error-passthrough would quarantine (or un-quarantine) a fair-value number
without a failing test. Network-free: fetch + profile are stubbed.
"""

from __future__ import annotations

import pytest

from gesh_core.dcf.inputs import DCFInputs
from gesh_core.dcf.sensitivity import run_sensitivity


def _ok_inputs(**overrides: object) -> DCFInputs:
    fields: dict[str, object] = {
        "symbol": "MPC",
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
    profile: tuple[float, bool, str | None] = (0.51, True, "Energy"),
) -> None:
    # compute_fair_value and run_sensitivity each bind these names at import.
    monkeypatch.setattr("gesh_core.dcf.fair_value.fetch_dcf_inputs", lambda symbol: data)
    monkeypatch.setattr("gesh_core.dcf.sensitivity.fetch_dcf_inputs", lambda symbol: data)
    monkeypatch.setattr("gesh_core.dcf.fair_value._fetch_profile", lambda symbol: profile)
    monkeypatch.setattr("gesh_core.dcf.sensitivity._fetch_profile", lambda symbol: profile)


def test_run_sensitivity_passthrough_when_base_dcf_refuses(monkeypatch):
    missing = DCFInputs(symbol="ZZZ", error="empty statements")
    _patch_fetch(monkeypatch, missing)
    out = run_sensitivity("ZZZ")
    assert out["symbol"] == "ZZZ"
    assert "error" in out
    assert "tornado" not in out
    assert "base_fair_value" not in out


def test_run_sensitivity_tornado_covers_assumption_probes(monkeypatch):
    _patch_fetch(monkeypatch, _ok_inputs())
    out = run_sensitivity("MPC")
    assert "error" not in out
    assert out["base_fair_value"] > 0
    assert 0 < out["wacc"] < 0.25

    variables = [row["variable"] for row in out["tornado"]]
    for required in (
        "ebitda_margin",
        "revenue_growth",
        "nwc_ratio",
        "capex_ratio",
        "terminal_growth",
        "wacc (via ERP)",
        "beta",
    ):
        assert required in variables

    swings = [row["swing"] for row in out["tornado"]]
    assert swings == sorted(swings, reverse=True)
    assert all(row["swing"] >= 0 for row in out["tornado"])


def test_run_sensitivity_bear_composite_is_a_revalued_price(monkeypatch):
    _patch_fetch(monkeypatch, _ok_inputs())
    out = run_sensitivity("MPC")
    assert out["bear_composite"] is not None
    assert out["bear_composite"] > 0
    assert "3yr-avg margin" in out["bear_composite_desc"]
    assert "straight-to-terminal" in out["bear_composite_desc"]


def test_run_sensitivity_beta_probe_uses_raw_and_market(monkeypatch):
    """The MPC failure mode: a 0.51 regression beta carried the whole valuation."""
    _patch_fetch(monkeypatch, _ok_inputs(), profile=(0.51, True, "Energy"))
    out = run_sensitivity("MPC")
    beta_row = next(row for row in out["tornado"] if row["variable"] == "beta")
    assert beta_row["low"] is not None
    assert beta_row["high"] is not None
    assert "0.51" in beta_row["low_desc"]
    assert "1.00" in beta_row["high_desc"]
    assert beta_row["swing"] > 0
