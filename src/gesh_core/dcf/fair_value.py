"""Deterministic DCF fair value — an auditable alternative to the LLM's estimate.

MEASUREMENT ONLY (rule #47). No trades, no DB writes, no gate impact. Nothing here is
wired into the :9000 product; it is a standalone engine-side tool.

The product's `fair_value_estimate` comes from Claude (`ai_analyzer.py` schema: "Your
fair-value estimate per share"), and `fair_value.canonical_pct_diff` turns it into the
`pct_diff` that drives the Kelly AI penalty and the holdings cards. That number is an
opinion with no shown work. This module produces one from statements instead, so the
two can be compared and the gap inspected.

WHAT IS FETCHED vs WHAT IS ASSUMED — the distinction that makes this auditable:
  fetched  (trading/dcf_inputs.py, yfinance statements):
             revenue, EBITDA, capex, NWC, tax rate, shares, net debt, beta
  assumed  (printed on every run, never silently baked in):
             revenue growth path, EBITDA margin path, terminal growth, equity risk
             premium, cost of debt, D/E

A DCF is only as good as its assumptions; this prints them so a wrong valuation is
traceable to a stated input rather than to a hidden constant (rules #45/#51/#59).

CLI:
    venv/bin/python3 -m trading.dcf_fair_value --symbol AMD
    venv/bin/python3 -m trading.dcf_fair_value --symbol AMD --terminal-growth 0.025 --json
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from gesh_core.dcf.inputs import fetch_dcf_inputs
from gesh_core.dcf.vendor.dcf_model import DCFModel as _VendoredDCFModel

# Stated assumptions — overridable from the CLI, never silent.
DEFAULT_TERMINAL_GROWTH = 0.03
DEFAULT_RISK_FREE = 0.042
DEFAULT_MARKET_PREMIUM = 0.055
DEFAULT_COST_OF_DEBT = 0.045
DEFAULT_DEBT_TO_EQUITY = 0.25
DEFAULT_BETA = 1.1
PROJECTION_YEARS = 5
# Guards on the percent-of-revenue projection method itself. Names above these bounds are
# balance-sheet stories (cash from raises, financing books), not revenue-scaled operators —
# the method is invalid there, so refuse rather than emit a negative "fair value".
# Re-derived 2026-08-08 for the OPERATING NWC basis (cash/ST-debt excluded): even
# long-cycle industrials rarely clear 40-50% of revenue, so 60% is a real bound with
# discriminating power, not the old blunt 100% backstop against a contaminated metric.
MAX_NWC_PCT_OF_REVENUE = 0.60
# Blunt interim rule, NOT a capex-sustainability judgment — a normalized-vs-D&A
# reframing (which would rescue fab supercycles like MU with a faded number instead of
# a refusal) is documented future work in the 2026-08-08 methodology review.
MAX_CAPEX_PCT_OF_REVENUE = 0.35
# NOPAT/percent-of-revenue DCF is conceptually wrong for balance sheets dominated by
# customer funds or lending books — named exclusion, not an NWC-guard accident.
_EXCLUDED_SECTORS = {"Financial Services", "Financials"}
# NOPAT-based FCF is meaningless for pre-scale names: with near-zero or negative
# EBITDA, projected working capital swamps earnings and the model emits a negative
# "price" (RKLB priced at -$10.67 the moment operating NWC let it through the old
# guards). The methodology review called this the separate, legitimate refusal ground.
MIN_EBITDA_MARGIN = 0.05
BETA_FRAGILE_SWING_PCT = 25.0


class _SeededDCFModel(_VendoredDCFModel):
    """DCFModel with the opening net-working-capital seeded from the real balance sheet.

    Upstream `project_cash_flows` opens with a hardcoded `prev_nwc = base_revenue * 0.10`
    and then reads NWC only through `assumptions["nwc_percent"]` — the `nwc` list passed
    to `set_historical_financials` is stored and never read. Same for capex, which is
    driven entirely by `assumptions["capex_percent"]` (default 5%).

    Measured on AMD FY2025: real capex is 2.81% of revenue against the 5% default
    (overstated 1.8x) and real NWC is 50.50% against the 10% default (understated 5.0x).
    Passing the true percentages fixes the levels, but the hardcoded 10% opening seed then
    manufactures a huge one-off year-1 working-capital swing — a name carrying 50% NWC
    would appear to consume 40% of revenue in year 1 alone, cratering FCF for no reason.

    So the percentages are supplied by the caller and the seed is corrected here. The
    vendored file stays byte-identical to upstream (see vendor/NOTICE.md) — this override
    is the documented place for GESH-specific corrections.
    """

    def project_cash_flows(self) -> dict[str, list[float]]:
        projections = super().project_cash_flows()
        historical_nwc = (self.historical_financials or {}).get("nwc") or []
        if not historical_nwc:
            return projections

        # Re-derive the NWC change series against the true opening balance, then rebuild
        # FCF. Every other line (revenue, ebitda, ebit, tax, nopat, capex) is unchanged.
        prev_nwc = float(historical_nwc[-1])
        nwc_changes: list[float] = []
        for i, revenue in enumerate(projections["revenue"]):
            nwc = revenue * self.assumptions["nwc_percent"][i]
            nwc_changes.append(nwc - prev_nwc)
            prev_nwc = nwc

        depreciation = projections["capex"]  # upstream sets D&A == capex by assumption
        projections["nwc_change"] = nwc_changes
        projections["fcf"] = [
            projections["nopat"][i] + depreciation[i] - projections["capex"][i] - nwc_changes[i]
            for i in range(len(nwc_changes))
        ]
        self.projections = projections
        return projections


def _fetch_profile(symbol: str) -> tuple[float, bool, str | None]:
    """(raw beta, was_fetched, sector). Falls back to DEFAULT_BETA and says so."""
    try:
        import yfinance as yf  # noqa: PLC0415

        info = yf.Ticker(symbol).info or {}
        sector = info.get("sector")
        beta = info.get("beta")
        if beta and 0 < float(beta) < 5:
            return float(beta), True, sector
        return DEFAULT_BETA, False, sector
    except Exception:  # noqa: BLE001 — rule #54; a missing profile must not abort the DCF
        return DEFAULT_BETA, False, None


def blume_beta(raw: float) -> float:
    """Blume-adjusted beta: 0.67*raw + 0.33*1.0 — the disclosed default input.

    A 2-year regression beta is a fragile estimator (mean-reverting, regime-dependent);
    on MPC the raw 0.508 single-handedly produced an +84% fair-value gap that collapsed
    to -1% at beta 1.0. Blume shrinkage is the standard, non-arbitrary correction —
    unlike a silent floor, both raw and adjusted are reported on every run.
    """
    return round(0.67 * raw + 0.33, 4)


def _avg_ratio(numerators: tuple[float, ...], revenue: tuple[float, ...]) -> float:
    """Mean of per-year ratios — the normalized base (latest year is a scenario now)."""
    ratios = [n / r for n, r in zip(numerators, revenue, strict=True) if r]
    return sum(ratios) / len(ratios)


def _growth_path(revenue: tuple[float, ...], terminal: float, years: int) -> list[float]:
    """Decay historical revenue CAGR toward terminal growth. An ASSUMPTION, not data."""
    if len(revenue) < 2 or revenue[0] <= 0:
        return [terminal] * years
    cagr = (revenue[-1] / revenue[0]) ** (1 / (len(revenue) - 1)) - 1
    start = max(min(cagr, 0.60), terminal)  # cap the extrapolated start at 60%
    return [start + (terminal - start) * (i / (years - 1)) for i in range(years)]


def value_with_assumptions(
    data: Any,
    beta: float,
    *,
    growth: list[float],
    margins: list[float],
    capex_pct: float,
    nwc_pct: float,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
    risk_free: float = DEFAULT_RISK_FREE,
    market_premium: float = DEFAULT_MARKET_PREMIUM,
    cost_of_debt: float = DEFAULT_COST_OF_DEBT,
    debt_to_equity: float = DEFAULT_DEBT_TO_EQUITY,
) -> dict[str, Any]:
    """Pure valuation core: DCFInputs + explicit assumptions -> fair value. No network.

    Extracted from compute_fair_value so sensitivity analysis can fetch statements ONCE
    and re-value under many assumption sets — re-fetching per scenario would be slow and,
    worse, could silently value different scenarios against different data. Callers are
    responsible for the method-validity guards; the only check here is the mathematical
    one (Gordon growth needs g < WACC — the vendored model does not guard it).
    """
    model = _SeededDCFModel(data.symbol)
    model.set_historical_financials(
        revenue=list(data.revenue), ebitda=list(data.ebitda),
        capex=list(data.capex), nwc=list(data.nwc), years=list(data.years),
    )
    model.set_assumptions(
        projection_years=PROJECTION_YEARS, revenue_growth=growth,
        ebitda_margin=margins, tax_rate=data.tax_rate, terminal_growth=terminal_growth,
        capex_percent=[capex_pct] * PROJECTION_YEARS,
        nwc_percent=[nwc_pct] * PROJECTION_YEARS,
    )
    wacc = model.calculate_wacc(
        risk_free_rate=risk_free, beta=beta, market_premium=market_premium,
        cost_of_debt=cost_of_debt, debt_to_equity=debt_to_equity,
    )
    if terminal_growth >= wacc:
        return {
            "error": f"terminal growth {terminal_growth:.2%} >= WACC {wacc:.2%} "
                     "— infinite value, mathematically invalid",
        }

    model.project_cash_flows()
    ev = model.calculate_enterprise_value()
    eq = model.calculate_equity_value(
        net_debt=data.net_debt, shares_outstanding=data.shares_outstanding
    )
    return {
        "fair_value_per_share": round(float(eq["value_per_share"]), 2),
        "enterprise_value_musd": round(float(ev["enterprise_value"]), 1),
        "equity_value_musd": round(float(eq["equity_value"]), 1),
        "terminal_pct_of_ev": round(float(ev["terminal_percent"]), 1),
        "wacc": round(wacc, 4),
    }


def compute_fair_value(
    symbol: str,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
    risk_free: float = DEFAULT_RISK_FREE,
    market_premium: float = DEFAULT_MARKET_PREMIUM,
    cost_of_debt: float = DEFAULT_COST_OF_DEBT,
    debt_to_equity: float = DEFAULT_DEBT_TO_EQUITY,
) -> dict[str, Any]:
    """Build a DCF from fetched statements. Returns an error dict if inputs are short."""
    data = fetch_dcf_inputs(symbol)
    if not data.available:
        return {
            "symbol": symbol,
            "error": data.error or f"missing inputs: {', '.join(data.missing)}",
            "fetched": False,
        }

    # `available` already implies these are populated — any None lands in `missing`.
    # Narrow explicitly anyway: it satisfies the type checker, and if the invariant ever
    # breaks we fail with a named error instead of a TypeError deep inside the model.
    tax_rate, shares, net_debt = data.tax_rate, data.shares_outstanding, data.net_debt
    if tax_rate is None or shares is None or net_debt is None:
        return {
            "symbol": symbol,
            "error": "incomplete inputs passed the availability check — "
                     "DCFInputs.available and its `missing` list are out of sync",
            "fetched": True,
        }

    raw_beta, beta_fetched, sector = _fetch_profile(symbol)
    if sector in _EXCLUDED_SECTORS:
        return {
            "symbol": symbol,
            "error": f"sector '{sector}' — NOPAT/percent-of-revenue DCF does not apply "
                     "to financial-sector balance sheets (customer funds/lending books)",
            "fetched": True,
        }
    beta = blume_beta(raw_beta) if beta_fetched else DEFAULT_BETA
    growth = _growth_path(data.revenue, terminal_growth, PROJECTION_YEARS)
    last_margin = data.ebitda[-1] / data.revenue[-1] if data.revenue[-1] else 0.20
    if last_margin < MIN_EBITDA_MARGIN:
        return {
            "symbol": symbol,
            "error": f"EBITDA margin {last_margin:.1%} (floor {MIN_EBITDA_MARGIN:.0%}) "
                     "— NOPAT-based FCF is not meaningful for a pre-scale business",
            "fetched": True,
        }
    margins = [last_margin] * PROJECTION_YEARS

    # Multi-year AVERAGE ratios are the base case (methodology review item 3): a single
    # latest-year point bakes a working-capital peak/trough into all five projection
    # years. "Latest year" is now a sensitivity scenario, not the headline.
    capex_pct = _avg_ratio(data.capex, data.revenue)
    nwc_pct = _avg_ratio(data.nwc, data.revenue)

    # A percent-of-revenue projection assumes revenue is the thing that scales working
    # capital and capex. That breaks for companies whose balance sheet dwarfs their
    # revenue: IONQ carries NWC at 1861% of revenue (raise proceeds, not operations), so
    # growing NWC with revenue consumes far more than the business earns and drives
    # enterprise value negative. Measured across the book, the model produced fair values
    # of -$40.88 (IONQ) and -$13.06 (RKLB) before this guard.
    if nwc_pct > MAX_NWC_PCT_OF_REVENUE:
        return {
            "symbol": symbol,
            "error": f"NWC is {nwc_pct:.0%} of revenue (limit {MAX_NWC_PCT_OF_REVENUE:.0%}) "
                     "— percent-of-revenue projection does not apply to this balance sheet",
            "fetched": True,
        }
    if capex_pct > MAX_CAPEX_PCT_OF_REVENUE:
        return {
            "symbol": symbol,
            "error": f"capex is {capex_pct:.0%} of revenue "
                     f"(limit {MAX_CAPEX_PCT_OF_REVENUE:.0%}) — not a sustainable "
                     "perpetuity assumption",
            "fetched": True,
        }

    core = value_with_assumptions(
        data, beta,
        growth=growth, margins=margins, capex_pct=capex_pct, nwc_pct=nwc_pct,
        terminal_growth=terminal_growth, risk_free=risk_free,
        market_premium=market_premium, cost_of_debt=cost_of_debt,
        debt_to_equity=debt_to_equity,
    )
    if core.get("error"):
        return {"symbol": symbol, "error": core["error"], "fetched": True}
    if core["fair_value_per_share"] <= 0:
        return {
            "symbol": symbol,
            "error": f"model produced a non-positive fair value "
                     f"(${core['fair_value_per_share']:,.2f}) — assumptions left the "
                     "valid region; refusing rather than publishing a negative price",
            "fetched": True,
        }

    # Beta fragility (methodology review item 1): one extra pure valuation at market
    # beta bounds how much of the number is the discount rate. fragile=True is the
    # display layer's cue that the headline depends materially on one regression
    # coefficient — the exact failure the MPC +84% turned out to be.
    beta_sensitivity: dict[str, Any] | None = None
    if beta_fetched:
        at_market = value_with_assumptions(
            data, 1.0, growth=growth, margins=margins,
            capex_pct=capex_pct, nwc_pct=nwc_pct,
            terminal_growth=terminal_growth, risk_free=risk_free,
            market_premium=market_premium, cost_of_debt=cost_of_debt,
            debt_to_equity=debt_to_equity,
        )
        if not at_market.get("error"):
            fv = core["fair_value_per_share"]
            swing = abs(at_market["fair_value_per_share"] - fv) / fv * 100 if fv else 0.0
            beta_sensitivity = {
                "fair_value_at_market_beta": at_market["fair_value_per_share"],
                "swing_pct": round(swing, 1),
                "fragile": swing > BETA_FRAGILE_SWING_PCT,
            }

    return {
        "symbol": symbol,
        "fetched": True,
        "beta_sensitivity": beta_sensitivity,
        **core,
        "inputs_fetched": {
            "years": list(data.years), "revenue": [round(v) for v in data.revenue],
            "ebitda": [round(v) for v in data.ebitda], "capex": [round(v) for v in data.capex],
            "tax_rate": data.tax_rate, "shares_m": data.shares_outstanding,
            "net_debt_musd": data.net_debt, "beta_raw": raw_beta,
            "beta": beta, "beta_is_blume_adjusted": beta_fetched,
            "beta_fetched": beta_fetched, "sector": sector,
        },
        "assumptions": {
            "revenue_growth": [round(g, 4) for g in growth],
            "ebitda_margin_flat": round(last_margin, 4),
            "terminal_growth": terminal_growth, "risk_free": risk_free,
            "market_premium": market_premium, "cost_of_debt": cost_of_debt,
            "debt_to_equity": debt_to_equity,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--terminal-growth", type=float, default=DEFAULT_TERMINAL_GROWTH)
    parser.add_argument("--risk-free", type=float, default=DEFAULT_RISK_FREE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = compute_fair_value(
        args.symbol.upper(),
        terminal_growth=args.terminal_growth,
        risk_free=args.risk_free,
    )
    if args.json:
        print(json.dumps(result, indent=2))
        return 1 if result.get("error") else 0

    if result.get("error"):
        print(f"\nDCF — {result['symbol']}: {result['error']}")
        return 1

    fetched, assumed = result["inputs_fetched"], result["assumptions"]
    print(f"\nDCF fair value — {result['symbol']}")
    print(f"  fair value/share : ${result['fair_value_per_share']:,.2f}")
    print(f"  enterprise value : ${result['enterprise_value_musd']:,.0f}M")
    print(f"  equity value     : ${result['equity_value_musd']:,.0f}M")
    print(f"  WACC             : {result['wacc']:.2%}")
    print(f"  terminal % of EV : {result['terminal_pct_of_ev']:.1f}%")
    print("\n  FETCHED (statements):")
    print(f"    years {fetched['years']}  revenue {fetched['revenue']}")
    print(f"    ebitda {fetched['ebitda']}  capex {fetched['capex']}")
    print(f"    tax {fetched['tax_rate']}  shares {fetched['shares_m']}M  "
          f"net_debt ${fetched['net_debt_musd']:,.0f}M")
    print(f"    beta {fetched['beta']}"
          f"{'' if fetched['beta_fetched'] else '  (DEFAULT — not fetched)'}")
    print("\n  ASSUMED (not data):")
    print(f"    revenue growth {[f'{g:.1%}' for g in assumed['revenue_growth']]}")
    print(f"    ebitda margin held flat at {assumed['ebitda_margin_flat']:.1%}")
    print(f"    terminal growth {assumed['terminal_growth']:.1%}  "
          f"risk-free {assumed['risk_free']:.1%}  ERP {assumed['market_premium']:.1%}")
    print("\n  MEASUREMENT ONLY — not wired to :9000, no trades, gate untouched (rule #47).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
