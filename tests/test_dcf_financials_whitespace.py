"""Financial-sector exclusion is case-insensitive and strips padding.

``compute_fair_value`` casefolds the Yahoo sector and compares against
``Financials`` / ``Financial Services``. Padded `` Financials `` must still
refuse — NOPAT/percent-of-revenue DCF does not apply to lending books.
"""

from __future__ import annotations

import pytest

from gesh_core.dcf.fair_value import compute_fair_value
from gesh_core.dcf.inputs import DCFInputs


def _ok_inputs(**overrides: object) -> DCFInputs:
    fields: dict[str, object] = {
        "symbol": "JPM",
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


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, profile) -> None:
    monkeypatch.setattr(
        "gesh_core.dcf.fair_value.fetch_dcf_inputs", lambda symbol: _ok_inputs()
    )
    monkeypatch.setattr("gesh_core.dcf.fair_value._fetch_profile", lambda symbol: profile)


@pytest.mark.parametrize("sector", ["Financials", "  Financials  ", "FINANCIALS"])
def test_padded_financials_alias_is_excluded(monkeypatch: pytest.MonkeyPatch, sector: str):
    _patch_fetch(monkeypatch, (1.0, True, sector))
    result = compute_fair_value("JPM")
    assert "error" in result
    assert "sector" in result["error"]
    assert "fair_value_per_share" not in result
