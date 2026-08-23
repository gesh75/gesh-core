"""Regression tests for the v0.8 NWC opening-seed correction.

Upstream `DCFModel.project_cash_flows` hardcodes `prev_nwc = base_revenue * 0.10`
and never reads the historical NWC series. A name carrying ~50% operating NWC then
appears to consume ~40% of revenue in year 1 alone, cratering FCF for no reason
(AMD FY2025 measurement in `_SeededDCFModel`). The override must keep every other
projection line identical to upstream.
"""

from __future__ import annotations

import pytest

from gesh_core.dcf.fair_value import _SeededDCFModel
from gesh_core.dcf.vendor.dcf_model import DCFModel


def _prime(
    model: DCFModel, *, nwc_last: float, revenue_last: float = 10_000.0, nwc_pct: float = 0.50
) -> DCFModel:
    model.set_historical_financials(
        revenue=[9_000.0, revenue_last],
        ebitda=[2_000.0, 2_500.0],
        capex=[400.0, 450.0],
        nwc=[nwc_last * 0.9, nwc_last],
        years=[2024, 2025],
    )
    model.set_assumptions(
        projection_years=5,
        revenue_growth=[0.05] * 5,
        ebitda_margin=[0.25] * 5,
        tax_rate=0.15,
        terminal_growth=0.03,
        capex_percent=[0.05] * 5,
        nwc_percent=[nwc_pct] * 5,
    )
    return model


def test_seeded_model_uses_historical_nwc_not_ten_percent_of_revenue():
    """Year-1 ΔNWC must start from the real closing NWC, not the 10% cookbook seed."""
    nwc_last = 5_000.0  # 50% of $10,000 revenue
    seeded = _prime(_SeededDCFModel("AMD"), nwc_last=nwc_last).project_cash_flows()
    vendored = _prime(DCFModel("AMD"), nwc_last=nwc_last).project_cash_flows()

    year1_revenue = 10_000.0 * 1.05
    year1_nwc = year1_revenue * 0.50
    assert seeded["nwc_change"][0] == pytest.approx(year1_nwc - nwc_last)
    # Cookbook seed is 10% of last revenue ($1,000) → a $4,250 manufactured swing.
    assert vendored["nwc_change"][0] == pytest.approx(year1_nwc - 10_000.0 * 0.10)
    assert seeded["nwc_change"][0] < vendored["nwc_change"][0]
    assert seeded["fcf"][0] > vendored["fcf"][0]


def test_seeded_model_leaves_non_nwc_lines_identical_to_upstream():
    seeded = _prime(_SeededDCFModel("AMD"), nwc_last=5_000.0).project_cash_flows()
    vendored = _prime(DCFModel("AMD"), nwc_last=5_000.0).project_cash_flows()
    for key in ("revenue", "ebitda", "ebit", "tax", "nopat", "capex"):
        assert seeded[key] == pytest.approx(vendored[key])


def test_seeded_model_without_historical_nwc_matches_upstream():
    """No NWC series → do not invent a seed; return the cookbook projection."""
    seeded = _SeededDCFModel("X")
    vendored = DCFModel("X")
    for model in (seeded, vendored):
        model.set_assumptions(
            projection_years=3,
            revenue_growth=[0.04] * 3,
            ebitda_margin=[0.20] * 3,
            capex_percent=[0.05] * 3,
            nwc_percent=[0.10] * 3,
        )
    assert seeded.project_cash_flows()["nwc_change"] == pytest.approx(
        vendored.project_cash_flows()["nwc_change"]
    )
    assert seeded.project_cash_flows()["fcf"] == pytest.approx(vendored.project_cash_flows()["fcf"])
