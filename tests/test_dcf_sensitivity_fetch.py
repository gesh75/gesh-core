"""run_sensitivity must fetch statements once and fail closed on empty inputs.

The function's contract is "Fetches once; error dict on refusal." Before the
fix it called compute_fair_value (network) and then fetch_dcf_inputs again.
A Yahoo 401/crumb miss on the second pull raised IndexError on
``data.revenue[-1]`` after a successful headline DCF, or valued the tornado
against a different fiscal series than the published base.
"""

from __future__ import annotations

from gesh_core.dcf.fair_value import PROJECTION_YEARS, compute_fair_value
from gesh_core.dcf.inputs import DCFInputs
from gesh_core.dcf.sensitivity import _base_assumptions, run_sensitivity


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

    profiles = {"n": 0}

    def boom_profile(symbol):
        profiles["n"] += 1
        raise AssertionError("unavailable statements must not pull a profile")

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
    monkeypatch.setattr(sensitivity, "_fetch_profile", boom_profile)
    monkeypatch.setattr(fair_value, "_fetch_profile", boom_profile)

    result = run_sensitivity("AMD")
    assert result.get("error")
    assert result["symbol"] == "AMD"
    assert "tornado" not in result
    assert profiles["n"] == 0


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


def test_run_sensitivity_ignores_a_second_snapshot_if_fetch_were_called_again(monkeypatch):
    """The original bug: headline from snapshot A, tornado from snapshot B.

    A second fetch that returns different fiscal years must not be consulted.
    """
    from gesh_core.dcf import fair_value, sensitivity

    first = _available_inputs()
    second = DCFInputs(
        symbol="AMD",
        years=(2010, 2011, 2012),
        revenue=(10.0, 11.0, 12.0),
        ebitda=(2.0, 2.2, 2.4),
        capex=(0.5, 0.55, 0.6),
        nwc=(1.0, 1.1, 1.2),
        tax_rate=0.21,
        shares_outstanding=100.0,
        net_debt=50.0,
    )
    snapshots = [first, second]
    fetches = {"n": 0}

    def fake_fetch(symbol, periods=3):
        data = snapshots[min(fetches["n"], len(snapshots) - 1)]
        fetches["n"] += 1
        return data

    profile = (1.2, True, "Technology")
    monkeypatch.setattr(sensitivity, "fetch_dcf_inputs", fake_fetch)
    monkeypatch.setattr(fair_value, "fetch_dcf_inputs", fake_fetch)
    monkeypatch.setattr(sensitivity, "_fetch_profile", lambda symbol: profile)
    monkeypatch.setattr(fair_value, "_fetch_profile", lambda symbol: profile)

    result = run_sensitivity("AMD")
    assert fetches["n"] == 1
    assert "error" not in result
    # Headline inputs must be the first snapshot's years, not 2010–2012.
    headline = compute_fair_value("AMD", data=first, profile=profile)
    assert result["base_fair_value"] == headline["fair_value_per_share"]


def test_base_assumptions_defaults_margin_when_latest_revenue_is_zero():
    """Lockstep with compute_fair_value: a 0 latest year must not divide by zero."""
    data = DCFInputs(
        symbol="AMD",
        years=(2023, 2024, 2025),
        revenue=(1000.0, 1100.0, 0.0),
        ebitda=(200.0, 220.0, 0.0),
        capex=(50.0, 55.0, 0.0),
        nwc=(100.0, 110.0, 0.0),
        tax_rate=0.21,
        shares_outstanding=100.0,
        net_debt=50.0,
    )
    base = _base_assumptions(data)
    assert base["margins"] == [0.20] * PROJECTION_YEARS


def test_compute_fair_value_reuses_injected_snapshot_without_fetching(monkeypatch):
    from gesh_core.dcf import fair_value

    def boom(*_args, **_kwargs):
        raise AssertionError("injected snapshot must not re-fetch")

    monkeypatch.setattr(fair_value, "fetch_dcf_inputs", boom)
    monkeypatch.setattr(fair_value, "_fetch_profile", boom)

    result = compute_fair_value(
        "AMD", data=_available_inputs(), profile=(1.1, False, "Technology")
    )
    assert "error" not in result
    assert result["fair_value_per_share"] > 0


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
