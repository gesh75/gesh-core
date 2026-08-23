"""Fundamental inputs for a real DCF — cash-flow, income and balance-sheet pull.

MEASUREMENT/ANALYSIS ONLY (rule #47). Read-only network fetch; places no trades and
writes no DB rows.

Why this exists: the product's `fair_value_estimate` is a field Claude fills in
(`ai_analyzer.py`: "Your fair-value estimate per share"). It is an LLM opinion, not a
model output, yet it drives `fair_value.canonical_pct_diff` -> the Kelly AI penalty ->
the holdings cards. This module fetches the statements a DCF actually needs so that
number can be produced deterministically and audited.

Source: yfinance. OpenBB is the repo's stated primary for fundamentals but is NOT
installed in this venv (CI excludes it — its resolver backtracks for 20+ min), so the
documented yfinance fallback tier is the real path here. Under the corporate VPN every
Yahoo host is SNI-blocked (rule #54) and this returns `available=False` rather than
guessing.

FABRICATION POLICY (rules #45/#51/#52/#56/#59). Every field is either fetched or
explicitly listed in `missing`. Nothing is defaulted to a plausible-looking constant:
a DCF built on an invented capex reads as a real valuation forever after. Callers must
check `.available` before using any figure.

CLI:
    python -m gesh_core.dcf.inputs --symbol AMD
    python -m gesh_core.dcf.inputs --symbol AMD --json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

# Row labels as yfinance presents them, in preference order.
_REVENUE_ROWS = ("Total Revenue", "Operating Revenue")
_EBITDA_ROWS = ("Normalized EBITDA", "EBITDA")
_CAPEX_ROWS = ("Capital Expenditure",)
_TAX_ROWS = ("Tax Rate For Calcs",)
_CUR_ASSET_ROWS = ("Current Assets",)
_CUR_LIAB_ROWS = ("Current Liabilities",)
# Operating-NWC exclusions (methodology review, 2026-08-08): cash/ST investments and
# ST debt are FINANCING items — including them made IONQ's "NWC" read 1861% of revenue
# (raise proceeds, not operations). Absent rows subtract as 0: many filers simply have
# no ST debt line, and treating absence as zero is the standard convention, not a guess.
_CASH_TOTAL_ROWS = ("Cash Cash Equivalents And Short Term Investments",)
_CASH_PART_ROWS = ("Cash And Cash Equivalents", "Other Short Term Investments")
_ST_DEBT_ROWS = ("Current Debt And Capital Lease Obligation", "Current Debt")
_CASH_ROWS = ("Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
_DEBT_ROWS = ("Total Debt",)
_SHARE_ROWS = ("Ordinary Shares Number", "Share Issued")

MIN_PERIODS = 3


@dataclass(frozen=True)
class DCFInputs:
    """Statement-derived DCF inputs. All monetary values in millions USD."""

    symbol: str
    years: tuple[int, ...] = ()
    revenue: tuple[float, ...] = ()
    ebitda: tuple[float, ...] = ()
    capex: tuple[float, ...] = ()
    nwc: tuple[float, ...] = ()
    tax_rate: float | None = None
    shares_outstanding: float | None = None   # millions
    net_debt: float | None = None             # millions; negative = net cash
    source: str = "yfinance"
    missing: tuple[str, ...] = ()
    error: str | None = None

    @property
    def available(self) -> bool:
        """True only when a DCF can actually be built from these figures.

        Length equality is part of the contract, not a detail: DCFModel consumes these
        as positional lists, so a short `nwc` beside a full `revenue` would pair the
        wrong fiscal years without raising.
        """
        series = (self.revenue, self.ebitda, self.capex, self.nwc)
        return (
            self.error is None
            and not self.missing
            and len(self.years) >= MIN_PERIODS
            and all(len(s) == len(self.years) for s in series)
        )


def _pick_row(frame: Any, candidates: tuple[str, ...]) -> Any | None:
    """First matching row from a statement frame, else None. Never guesses."""
    if frame is None or getattr(frame, "empty", True):
        return None
    for label in candidates:
        if label in frame.index:
            return frame.loc[label]
    return None


def _row_by_date(
    frame: Any, candidates: tuple[str, ...], absolute: bool = False
) -> dict[str, float] | None:
    """Map period-end date -> value (millions), dropping NaN. None if the row is absent.

    Keyed by DATE, never by list position. Dropping NaN positionally and then indexing
    across two series silently subtracts different fiscal years the moment one statement
    has a gap the other does not — the same defect `gesh_core.kelly._fetch_returns`
    documents ("positional alignment misdated every series with a gap"). Verified here:
    with a NaN in current-assets and `--periods 5`, positional alignment computed a 2025
    NWC of 26.0 by subtracting 2024 liabilities from 2025 assets, instead of 25.0.
    """
    row = _pick_row(frame, candidates)
    if row is None:
        return None
    out: dict[str, float] = {}
    for col, value in zip(frame.columns, row.tolist(), strict=False):
        if value is None or value != value:  # NaN
            continue
        scaled = float(value) / 1e6
        out[str(col)[:10]] = abs(scaled) if absolute else scaled
    return out or None


def _newest_value(frame: Any, candidates: tuple[str, ...], scale: float = 1.0) -> float | None:
    """Most recent non-NaN value of a row, unscaled by periods."""
    row = _pick_row(frame, candidates)
    if row is None:
        return None
    for value in row.tolist():  # yfinance is newest-first
        if value is not None and value == value:
            return float(value) / scale
    return None


def fetch_dcf_inputs(symbol: str, periods: int = 3) -> DCFInputs:
    """Pull statements and derive DCF inputs. Missing fields are reported, not invented."""
    try:
        import yfinance as yf  # noqa: PLC0415

        ticker = yf.Ticker(symbol)
        income = ticker.financials
        cash = ticker.cashflow
        balance = ticker.balance_sheet
    except Exception as exc:  # noqa: BLE001 — network/VPN failure is expected (rule #54)
        return DCFInputs(symbol=symbol, error=f"{type(exc).__name__}: {exc}")

    if any(getattr(f, "empty", True) for f in (income, cash, balance)):
        return DCFInputs(
            symbol=symbol,
            error="empty statements (Yahoo unreachable, or no coverage for this symbol)",
        )

    missing: list[str] = []

    # Every per-period series, keyed by statement date. `capex` comes from the cash-flow
    # statement and NWC from the balance sheet, so these span three frames whose columns
    # are NOT guaranteed to agree — intersecting the dates below is what makes a
    # revenue/capex pair refer to the same fiscal year.
    by_date: dict[str, dict[str, float] | None] = {
        "revenue": _row_by_date(income, _REVENUE_ROWS),
        "ebitda": _row_by_date(income, _EBITDA_ROWS),
        "capex": _row_by_date(cash, _CAPEX_ROWS, absolute=True),
        "cur_assets": _row_by_date(balance, _CUR_ASSET_ROWS),
        "cur_liab": _row_by_date(balance, _CUR_LIAB_ROWS),
    }
    for name, series in by_date.items():
        if series is None:
            # cur_assets and cur_liab are two halves of one derived field; report it once.
            label = "nwc" if name in ("cur_assets", "cur_liab") else name
            if label not in missing:
                missing.append(label)

    present = [s for s in by_date.values() if s]
    common = set(present[0]).intersection(*present[1:]) if present else set()
    # Newest `periods` dates that every series actually covers, then oldest-first.
    dates = sorted(sorted(common, reverse=True)[:periods])
    if len(dates) < MIN_PERIODS:
        missing.append(f"aligned_periods({len(dates)}<{MIN_PERIODS})")

    def _col(name: str) -> tuple[float, ...]:
        series = by_date[name]
        return tuple(series[d] for d in dates) if series else ()

    revenue, ebitda, capex = _col("revenue"), _col("ebitda"), _col("capex")
    # NWC needs BOTH component rows. With one absent, `_col` returns () for it while the
    # other still spans `dates` — a strict zip then raises ValueError instead of the
    # graceful `missing` report this module promises (found by adversarial review, which
    # reproduced the crash with an asymmetric balance-sheet frame). When both are present
    # they are each defined on every date in `dates` by construction, so strict=True is a
    # true invariant there, not a hope.
    if by_date["cur_assets"] and by_date["cur_liab"]:
        assets, liabilities = _col("cur_assets"), _col("cur_liab")

        def _optional(rows: tuple[str, ...]) -> tuple[float, ...]:
            series = _row_by_date(balance, rows)
            return tuple((series or {}).get(d, 0.0) for d in dates)

        # Prefer the combined cash+ST-investments total; fall back to summing parts.
        cash_like = _optional(_CASH_TOTAL_ROWS)
        if not any(cash_like):
            parts = [_optional((r,)) for r in _CASH_PART_ROWS]
            cash_like = tuple(sum(vals) for vals in zip(*parts, strict=True))
        st_debt = _optional(_ST_DEBT_ROWS)
        nwc = tuple(
            (a - c) - (liability - d)
            for a, c, liability, d in zip(assets, cash_like, liabilities, st_debt, strict=True)
        )
    else:
        nwc = ()

    tax_rate = _newest_value(income, _TAX_ROWS)
    if tax_rate is None:
        missing.append("tax_rate")

    shares = _newest_value(balance, _SHARE_ROWS, scale=1e6)
    if shares is None:
        missing.append("shares_outstanding")

    total_debt = _newest_value(balance, _DEBT_ROWS, scale=1e6)
    cash_on_hand = _newest_value(balance, _CASH_ROWS, scale=1e6)
    net_debt = None if total_debt is None or cash_on_hand is None else total_debt - cash_on_hand
    if net_debt is None:
        missing.append("net_debt")

    years = tuple(int(d[:4]) for d in dates)

    return DCFInputs(
        symbol=symbol,
        years=years,
        revenue=revenue,
        ebitda=ebitda,
        capex=capex,
        nwc=nwc,
        tax_rate=tax_rate,
        shares_outstanding=shares,
        net_debt=net_debt,
        missing=tuple(missing),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--periods", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = fetch_dcf_inputs(args.symbol.upper(), args.periods)
    if args.json:
        print(json.dumps({**asdict(data), "available": data.available}, indent=2))
        return 0 if data.available else 1

    print(f"\nDCF inputs — {data.symbol}   (source: {data.source}, $M)")
    if data.error:
        print(f"  ERROR: {data.error}")
        return 1
    print(f"  years            : {', '.join(map(str, data.years))}")
    print(f"  revenue          : {[round(v) for v in data.revenue]}")
    print(f"  ebitda           : {[round(v) for v in data.ebitda]}")
    print(f"  capex            : {[round(v) for v in data.capex]}")
    print(f"  nwc              : {[round(v) for v in data.nwc]}")
    print(f"  tax_rate         : {data.tax_rate}")
    print(f"  shares (M)       : {data.shares_outstanding}")
    print(f"  net_debt ($M)    : {data.net_debt}"
          f"{'  (net cash)' if (data.net_debt or 0) < 0 else ''}")
    if data.missing:
        print(f"  MISSING          : {', '.join(data.missing)}  -> DCF not buildable")
    print(f"  available        : {data.available}")
    return 0 if data.available else 1


if __name__ == "__main__":
    raise SystemExit(main())
