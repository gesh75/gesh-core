"""Characterization tests for DCF statement parsing (v0.8.0 methodology).

`gesh_core.dcf` shipped without in-repo fetch tests. Open PR #35 covers the
valuation guards; this file pins the *input* contract that those guards consume:

  - date-keyed alignment (a NaN in one year must not pair the wrong fiscal years)
  - operating NWC (cash / ST investments / ST debt are financing, not operations)
  - missing fields are reported, never invented
  - network/empty statements fail closed

Network-free: yfinance.Ticker is stubbed with in-memory statement frames.
"""
from __future__ import annotations

import pandas as pd
import pytest
import yfinance as yf

from gesh_core.dcf.fair_value import DEFAULT_BETA, _fetch_profile
from gesh_core.dcf.inputs import (
    MIN_PERIODS,
    DCFInputs,
    _newest_value,
    _pick_row,
    _row_by_date,
    fetch_dcf_inputs,
)


def _stmt(rows: dict[str, dict[str, float]]) -> pd.DataFrame:
    """Build a yfinance-shaped statement: row labels × newest-first date columns."""
    dates = sorted({d for series in rows.values() for d in series}, reverse=True)
    data = [[series.get(d, float("nan")) for d in dates] for series in rows.values()]
    return pd.DataFrame(data, index=list(rows), columns=[pd.Timestamp(d) for d in dates])


class _Ticker:
    def __init__(self, income: pd.DataFrame, cash: pd.DataFrame, balance: pd.DataFrame):
        self.financials = income
        self.cashflow = cash
        self.balance_sheet = balance


def _patch_ticker(monkeypatch: pytest.MonkeyPatch, income, cash, balance) -> None:
    monkeypatch.setattr(yf, "Ticker", lambda symbol: _Ticker(income, cash, balance))


def _complete_statements(
    *,
    extra_income: dict[str, dict[str, float]] | None = None,
    extra_cash: dict[str, dict[str, float]] | None = None,
    extra_balance: dict[str, dict[str, float]] | None = None,
    omit_balance: tuple[str, ...] = (),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    income_rows: dict[str, dict[str, float]] = {
        "Total Revenue": {
            "2023-12-31": 20_000e6, "2024-12-31": 22_000e6, "2025-12-31": 25_000e6,
        },
        "Normalized EBITDA": {
            "2023-12-31": 5_000e6, "2024-12-31": 6_000e6, "2025-12-31": 7_500e6,
        },
        "Tax Rate For Calcs": {
            "2023-12-31": 0.14, "2024-12-31": 0.15, "2025-12-31": 0.16,
        },
    }
    cash_rows: dict[str, dict[str, float]] = {
        "Capital Expenditure": {
            "2023-12-31": -1_000e6, "2024-12-31": -1_100e6, "2025-12-31": -1_250e6,
        },
    }
    balance_rows: dict[str, dict[str, float]] = {
        "Current Assets": {
            "2023-12-31": 8_000e6, "2024-12-31": 9_000e6, "2025-12-31": 10_000e6,
        },
        "Current Liabilities": {
            "2023-12-31": 3_000e6, "2024-12-31": 3_500e6, "2025-12-31": 4_000e6,
        },
        "Cash Cash Equivalents And Short Term Investments": {
            "2023-12-31": 2_000e6, "2024-12-31": 2_500e6, "2025-12-31": 3_000e6,
        },
        "Current Debt And Capital Lease Obligation": {
            "2023-12-31": 500e6, "2024-12-31": 800e6, "2025-12-31": 1_000e6,
        },
        "Ordinary Shares Number": {
            "2023-12-31": 1_500e6, "2024-12-31": 1_550e6, "2025-12-31": 1_600e6,
        },
        "Total Debt": {
            "2023-12-31": 5_000e6, "2024-12-31": 4_500e6, "2025-12-31": 4_000e6,
        },
        "Cash And Cash Equivalents": {
            "2023-12-31": 1_500e6, "2024-12-31": 1_800e6, "2025-12-31": 2_000e6,
        },
    }
    if extra_income:
        income_rows.update(extra_income)
    if extra_cash:
        cash_rows.update(extra_cash)
    if extra_balance:
        balance_rows.update(extra_balance)
    for label in omit_balance:
        balance_rows.pop(label, None)
    return _stmt(income_rows), _stmt(cash_rows), _stmt(balance_rows)


# ─── row helpers (no network, no Ticker) ──────────────────────────────────────


def test_pick_row_prefers_first_matching_label():
    frame = _stmt({
        "Operating Revenue": {"2025-12-31": 1e6},
        "Total Revenue": {"2025-12-31": 9e6},
    })
    row = _pick_row(frame, ("Total Revenue", "Operating Revenue"))
    assert row is not None
    assert float(row.iloc[0]) == pytest.approx(9e6)


def test_pick_row_returns_none_for_empty_or_unknown():
    assert _pick_row(None, ("Total Revenue",)) is None
    assert _pick_row(pd.DataFrame(), ("Total Revenue",)) is None
    frame = _stmt({"EBITDA": {"2025-12-31": 1e6}})
    assert _pick_row(frame, ("Total Revenue", "Operating Revenue")) is None


def test_row_by_date_keys_by_period_end_and_skips_nan():
    frame = _stmt({
        "Current Assets": {
            "2023-12-31": 30e6, "2024-12-31": float("nan"), "2025-12-31": 50e6,
        },
    })
    out = _row_by_date(frame, ("Current Assets",))
    assert out == {"2023-12-31": pytest.approx(30.0), "2025-12-31": pytest.approx(50.0)}
    assert "2024-12-31" not in out


def test_row_by_date_capex_is_absolute():
    frame = _stmt({"Capital Expenditure": {"2025-12-31": -1_250e6}})
    out = _row_by_date(frame, ("Capital Expenditure",), absolute=True)
    assert out == {"2025-12-31": pytest.approx(1_250.0)}


def test_newest_value_skips_leading_nan():
    frame = _stmt({
        "Tax Rate For Calcs": {
            "2023-12-31": 0.14, "2024-12-31": 0.15, "2025-12-31": float("nan"),
        },
    })
    assert _newest_value(frame, ("Tax Rate For Calcs",)) == pytest.approx(0.15)


# ─── fetch_dcf_inputs (Ticker stubbed) ────────────────────────────────────────


def test_fetch_builds_operating_nwc_not_headline_current_nwc(monkeypatch):
    """Cash / ST investments / ST debt are financing — they must leave NWC."""
    _patch_ticker(monkeypatch, *_complete_statements())
    data = fetch_dcf_inputs("AMD")
    assert data.available is True
    assert data.years == (2023, 2024, 2025)
    assert data.revenue == pytest.approx((20_000.0, 22_000.0, 25_000.0))
    assert data.ebitda == pytest.approx((5_000.0, 6_000.0, 7_500.0))
    assert data.capex == pytest.approx((1_000.0, 1_100.0, 1_250.0))
    # (CA - cash_like) - (CL - ST debt): 2025 = (10000-3000) - (4000-1000) = 4000
    assert data.nwc == pytest.approx((3_500.0, 3_800.0, 4_000.0))
    assert data.tax_rate == pytest.approx(0.16)
    assert data.shares_outstanding == pytest.approx(1_600.0)
    # net_debt uses Cash And Cash Equivalents (first _CASH_ROWS match), newest year
    assert data.net_debt == pytest.approx(2_000.0)
    assert data.missing == ()


def test_nan_in_one_year_does_not_cross_pair_fiscal_years(monkeypatch):
    """The documented positional-alignment defect: a 2024 assets NaN used to
    subtract 2024 liabilities from 2025 assets. Date keys must drop 2024 only."""
    income = _stmt({
        "Total Revenue": {
            "2022-12-31": 18_000e6, "2023-12-31": 20_000e6,
            "2024-12-31": 22_000e6, "2025-12-31": 25_000e6,
        },
        "Normalized EBITDA": {
            "2022-12-31": 4_000e6, "2023-12-31": 5_000e6,
            "2024-12-31": 6_000e6, "2025-12-31": 7_500e6,
        },
        "Tax Rate For Calcs": {"2025-12-31": 0.16},
    })
    cash = _stmt({
        "Capital Expenditure": {
            "2022-12-31": -900e6, "2023-12-31": -1_000e6,
            "2024-12-31": -1_100e6, "2025-12-31": -1_250e6,
        },
    })
    balance = _stmt({
        "Current Assets": {
            "2022-12-31": 35e6, "2023-12-31": 40e6,
            "2024-12-31": float("nan"), "2025-12-31": 50e6,
        },
        "Current Liabilities": {
            "2022-12-31": 18e6, "2023-12-31": 20e6,
            "2024-12-31": 24e6, "2025-12-31": 25e6,
        },
        "Ordinary Shares Number": {"2025-12-31": 1_600e6},
        "Total Debt": {"2025-12-31": 4_000e6},
        # Zero cash on the aligned years only — financing subtracts as 0 so
        # NWC == CA - CL, and a scale mismatch cannot hide a year-pairing bug.
        "Cash And Cash Equivalents": {
            "2022-12-31": 0.0, "2023-12-31": 0.0, "2025-12-31": 0.0,
        },
    })
    _patch_ticker(monkeypatch, income, cash, balance)
    data = fetch_dcf_inputs("AMD", periods=5)
    assert 2024 not in data.years
    # Newest 3 *aligned* years: 2022, 2023, 2025 — cash/ST debt absent → 0.
    assert data.years == (2022, 2023, 2025)
    assert data.nwc[-1] == pytest.approx(25.0)  # 50 - 25, not 50 - 24
    assert data.nwc == pytest.approx((17.0, 20.0, 25.0))
    assert data.available is True


def test_asymmetric_balance_sheet_reports_missing_nwc_without_raising(monkeypatch):
    income, cash, balance = _complete_statements(omit_balance=("Current Assets",))
    _patch_ticker(monkeypatch, income, cash, balance)
    data = fetch_dcf_inputs("AMD")
    assert data.available is False
    assert "nwc" in data.missing
    assert data.nwc == ()
    assert data.error is None


def test_absent_st_debt_is_zero_not_a_guess(monkeypatch):
    income, cash, balance = _complete_statements(
        omit_balance=("Current Debt And Capital Lease Obligation",),
    )
    _patch_ticker(monkeypatch, income, cash, balance)
    data = fetch_dcf_inputs("AMD")
    assert data.available is True
    # 2025: (10000-3000) - (4000-0) = 3000
    assert data.nwc[-1] == pytest.approx(3_000.0)


def test_cash_parts_sum_when_combined_row_absent(monkeypatch):
    income, cash, balance = _complete_statements(
        omit_balance=("Cash Cash Equivalents And Short Term Investments",),
        extra_balance={
            "Other Short Term Investments": {
                "2023-12-31": 500e6, "2024-12-31": 700e6, "2025-12-31": 1_000e6,
            },
        },
    )
    _patch_ticker(monkeypatch, income, cash, balance)
    data = fetch_dcf_inputs("AMD")
    assert data.available is True
    # cash_like 2025 = 2000 (Cash) + 1000 (ST investments) = 3000 — same as combined
    assert data.nwc[-1] == pytest.approx(4_000.0)


def test_empty_statements_are_unavailable(monkeypatch):
    empty = pd.DataFrame()
    _patch_ticker(monkeypatch, empty, empty, empty)
    data = fetch_dcf_inputs("ZZZ")
    assert data.available is False
    assert data.error is not None
    assert "empty statements" in data.error
    assert data.missing == ()


def test_ticker_exception_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(yf, "Ticker", lambda symbol: (_ for _ in ()).throw(RuntimeError("sni")))
    data = fetch_dcf_inputs("AMD")
    assert data.available is False
    assert data.error is not None
    assert "RuntimeError" in data.error
    assert "fair_value" not in (data.error or "")


def test_too_few_aligned_periods_are_listed_in_missing(monkeypatch):
    income = _stmt({
        "Total Revenue": {"2025-12-31": 25_000e6, "2024-12-31": 22_000e6},
        "Normalized EBITDA": {"2025-12-31": 7_500e6, "2024-12-31": 6_000e6},
        "Tax Rate For Calcs": {"2025-12-31": 0.16},
    })
    cash = _stmt({
        "Capital Expenditure": {"2025-12-31": -1_250e6, "2024-12-31": -1_100e6},
    })
    balance = _stmt({
        "Current Assets": {"2025-12-31": 10_000e6, "2024-12-31": 9_000e6},
        "Current Liabilities": {"2025-12-31": 4_000e6, "2024-12-31": 3_500e6},
        "Ordinary Shares Number": {"2025-12-31": 1_600e6},
        "Total Debt": {"2025-12-31": 4_000e6},
        "Cash And Cash Equivalents": {"2025-12-31": 2_000e6},
    })
    _patch_ticker(monkeypatch, income, cash, balance)
    data = fetch_dcf_inputs("AMD")
    assert data.available is False
    assert any(m.startswith(f"aligned_periods(2<{MIN_PERIODS})") for m in data.missing)


def test_missing_tax_shares_or_debt_are_named(monkeypatch):
    income, cash, balance = _complete_statements(
        omit_balance=("Ordinary Shares Number", "Total Debt", "Cash And Cash Equivalents"),
    )
    # Drop tax row by rebuilding income without it.
    income = _stmt({
        "Total Revenue": {
            "2023-12-31": 20_000e6, "2024-12-31": 22_000e6, "2025-12-31": 25_000e6,
        },
        "Normalized EBITDA": {
            "2023-12-31": 5_000e6, "2024-12-31": 6_000e6, "2025-12-31": 7_500e6,
        },
    })
    _patch_ticker(monkeypatch, income, cash, balance)
    data = fetch_dcf_inputs("AMD")
    assert data.available is False
    assert "tax_rate" in data.missing
    assert "shares_outstanding" in data.missing
    assert "net_debt" in data.missing
    assert data.tax_rate is None
    assert data.shares_outstanding is None
    assert data.net_debt is None


def test_operating_revenue_fallback_when_total_revenue_absent(monkeypatch):
    income, cash, balance = _complete_statements()
    income = _stmt({
        "Operating Revenue": {
            "2023-12-31": 19_000e6, "2024-12-31": 21_000e6, "2025-12-31": 24_000e6,
        },
        "Normalized EBITDA": {
            "2023-12-31": 5_000e6, "2024-12-31": 6_000e6, "2025-12-31": 7_500e6,
        },
        "Tax Rate For Calcs": {"2025-12-31": 0.16},
    })
    _patch_ticker(monkeypatch, income, cash, balance)
    data = fetch_dcf_inputs("AMD")
    assert data.available is True
    assert data.revenue == pytest.approx((19_000.0, 21_000.0, 24_000.0))


def test_available_requires_aligned_lengths():
    short = DCFInputs(
        symbol="X",
        years=(2024, 2025),
        revenue=(1.0, 2.0),
        ebitda=(1.0, 2.0),
        capex=(0.1, 0.2),
        nwc=(0.2, 0.3),
        tax_rate=0.2,
        shares_outstanding=10.0,
        net_debt=0.0,
    )
    assert short.available is False
    assert MIN_PERIODS == 3


# ─── profile fetch (beta bounds) ──────────────────────────────────────────────


def test_fetch_profile_accepts_in_range_beta(monkeypatch):
    monkeypatch.setattr(
        yf, "Ticker",
        lambda symbol: type("T", (), {"info": {"beta": 1.25, "sector": "Technology"}})(),
    )
    beta, fetched, sector = _fetch_profile("AMD")
    assert (beta, fetched, sector) == (1.25, True, "Technology")


@pytest.mark.parametrize("beta", [None, 0, 0.0, 5.0, 6.2, -0.4])
def test_fetch_profile_rejects_unusable_beta(monkeypatch, beta):
    monkeypatch.setattr(
        yf, "Ticker",
        lambda symbol, _beta=beta: type("T", (), {"info": {"beta": _beta, "sector": "Tech"}})(),
    )
    raw, fetched, sector = _fetch_profile("AMD")
    assert raw == DEFAULT_BETA
    assert fetched is False
    assert sector == "Tech"


def test_fetch_profile_exception_falls_back_without_sector(monkeypatch):
    monkeypatch.setattr(yf, "Ticker", lambda symbol: (_ for _ in ()).throw(OSError("vpn")))
    raw, fetched, sector = _fetch_profile("AMD")
    assert (raw, fetched, sector) == (DEFAULT_BETA, False, None)
