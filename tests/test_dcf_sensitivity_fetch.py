"""run_sensitivity must fetch statements once and fail closed on empty inputs.

The function's contract is "Fetches once; error dict on refusal." Before the
fix it called compute_fair_value (network) and then fetch_dcf_inputs again.
A Yahoo 401/crumb miss on the second pull raised IndexError on
``data.revenue[-1]`` after a successful headline DCF, or valued the tornado
against a different fiscal series than the published base.
"""

from __future__ import annotations

from gesh_core.dcf.fair_value import compute_fair_value
from gesh_core.dcf.inputs import DCFInputs
from gesh_core.dcf.sensitivity import run_sensitivity


def _available_inputs(symbol: str = "AMD") -> DCFInputs:
    return DCFInputs(
        symbol=symbol,
        years=(2023, 2024, 2025),
        revenue=(1000.0, 1100.0, 1200.0),
        ebitda=(200.0, 220.0, 240.0),
        capex=(50.0, 55.0, 60.0),
        nwc=(100.0, 110.0, 120.0),
        tax_rate=0.21,
        shares_outstanding=100.0,
        net_debt=50.0,
    )


def test_run_sensitivity_unavailable_inputs_returns_error_not_crash(monkeypatch):
    """Empty/failed statement pull must return an error dict, not IndexError."""
    from gesh_core.dcf import fair_value, sensitivity

    monkeypatch.setattr(
        sensitivity,
        "fetch_dcf_inputs",
        lambda symbol, periods=3: DCFInputs(symbol=symbol, error="empty statements"),
    )
    monkeypatch.setattr(
        fair_value,
        "fetch_dcf_inputs",
        lambda symbol, periods=3: DCFInputs(symbol=symbol, error="empty statements"),
    )

    result = run_sensitivity("AMD")
    assert result.get("error")
    assert result["symbol"] == "AMD"
    assert "tornado" not in result


def test_run_sensitivity_fetches_statements_and_profile_once(monkeypatch):
    from gesh_core.dcf import fair_value, sensitivity

    fetches = {"n": 0}
    profiles = {"n": 0}
    data = _available_inputs()
    profile = (1.2, True, "Technology")

    def fake_fetch(symbol, periods=3):
        fetches["n"] += 1
        return data

    def fake_profile(symbol):
        profiles["n"] += 1
        return profile

    monkeypatch.setattr(sensitivity, "fetch_dcf_inputs", fake_fetch)
    monkeypatch.setattr(fair_value, "fetch_dcf_inputs", fake_fetch)
    monkeypatch.setattr(sensitivity, "_fetch_profile", fake_profile)
    monkeypatch.setattr(fair_value, "_fetch_profile", fake_profile)

    result = run_sensitivity("AMD")
    assert fetches["n"] == 1
    assert profiles["n"] == 1
    assert "error" not in result
    assert result["base_fair_value"] > 0
    assert {row["variable"] for row in result["tornado"]} >= {
        "ebitda_margin",
        "beta",
        "nwc_ratio",
    }


def test_compute_fair_value_without_kwargs_still_self_fetches(monkeypatch):
    from gesh_core.dcf import fair_value

    fetches = {"n": 0}
    profiles = {"n": 0}

    def fake_fetch(symbol, periods=3):
        fetches["n"] += 1
        return _available_inputs(symbol)

    def fake_profile(symbol):
        profiles["n"] += 1
        return (1.1, False, None)

    monkeypatch.setattr(fair_value, "fetch_dcf_inputs", fake_fetch)
    monkeypatch.setattr(fair_value, "_fetch_profile", fake_profile)

    result = compute_fair_value("AMD")
    assert fetches["n"] == 1
    assert profiles["n"] == 1
    assert "error" not in result
    assert result["fair_value_per_share"] > 0
