"""DCF sensitivity — bound how much of a fair-value gap is assumption, not signal.

MEASUREMENT ONLY (rule #47). No trades, no DB writes, no gate impact.

Why this exists: the deterministic DCF read MPC at +84% vs market. Adversarial review
(PR #104, F4) identified three compounding structural biases for cyclical names, all
code-verified: `_growth_path` extrapolates a 3-year revenue CAGR; the EBITDA margin is
the single latest year held flat for 5; the NWC ratio likewise. For a refiner coming off
an upcycle year, all three push the same direction and compound through a Gordon terminal
value that dominates EV. Until the number survives those probes, it is quarantined from
decisions.

This module fetches statements ONCE, then re-values through the pure core
(`value_with_assumptions`) under perturbed assumptions:

  tornado   — one variable at a time (margin, growth path, NWC ratio, capex ratio,
              terminal growth, WACC via ERP), ranked by swing
  composite — the honest bear case: 3-yr AVERAGE margin + straight-to-terminal growth
              + 3-yr average NWC/capex ratios, all at once

The base case is derived by the same code `compute_fair_value` uses, so the tornado's
center is guaranteed to be the number being audited, not a near-copy of it.

CLI:
    venv/bin/python3 -m trading.dcf_sensitivity --symbol MPC
    venv/bin/python3 -m trading.dcf_sensitivity --symbol MPC --json
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from gesh_core.dcf.fair_value import (
    DEFAULT_MARKET_PREMIUM,
    DEFAULT_TERMINAL_GROWTH,
    PROJECTION_YEARS,
    _avg_ratio,
    _fetch_profile,
    _growth_path,
    blume_beta,
    compute_fair_value,
    value_with_assumptions,
)
from gesh_core.dcf.inputs import DCFInputs, fetch_dcf_inputs


def _base_assumptions(data: DCFInputs) -> dict[str, Any]:
    """Exactly the derivation compute_fair_value performs — kept in lockstep by test.

    Base = multi-year AVERAGE capex/NWC ratios since the 2026-08-08 methodology
    review; latest-year is the scenario now, not the headline.
    """
    base_revenue = data.revenue[-1]
    return {
        "growth": _growth_path(data.revenue, DEFAULT_TERMINAL_GROWTH, PROJECTION_YEARS),
        "margins": [data.ebitda[-1] / base_revenue] * PROJECTION_YEARS,
        "capex_pct": _avg_ratio(data.capex, data.revenue),
        "nwc_pct": _avg_ratio(data.nwc, data.revenue),
    }


def run_sensitivity(symbol: str) -> dict[str, Any]:
    """Tornado + bear-composite around the base DCF. Fetches once; error dict on refusal."""
    # One statement pull + one profile pull, then every scenario re-values that
    # same snapshot. A second Yahoo call here used to crash on empty revenue
    # (`data.revenue[-1]`) after a successful headline DCF, or silently tornado
    # a different fiscal series than the published base (the failure
    # value_with_assumptions was extracted to prevent).
    data = fetch_dcf_inputs(symbol)
    if not data.available:
        base_result = compute_fair_value(symbol, data=data)
        return {"symbol": symbol, "error": base_result.get("error") or "inputs unavailable"}
    profile = _fetch_profile(symbol)
    base_result = compute_fair_value(symbol, data=data, profile=profile)
    if base_result.get("error"):
        return {"symbol": symbol, "error": base_result["error"]}

    raw_beta, beta_fetched, _sector = profile
    beta = blume_beta(raw_beta) if beta_fetched else raw_beta
    base = _base_assumptions(data)
    base_fv = base_result["fair_value_per_share"]

    def value(**overrides: Any) -> float | None:
        merged = {**base, **{k: v for k, v in overrides.items() if not k.startswith("_")}}
        out = value_with_assumptions(
            data, overrides.get("_beta", beta),
            growth=merged["growth"], margins=merged["margins"],
            capex_pct=merged["capex_pct"], nwc_pct=merged["nwc_pct"],
            terminal_growth=overrides.get("_terminal", DEFAULT_TERMINAL_GROWTH),
            market_premium=overrides.get("_erp", DEFAULT_MARKET_PREMIUM),
        )
        return None if out.get("error") else out["fair_value_per_share"]

    avg_margin = _avg_ratio(data.ebitda, data.revenue)
    min_margin = min(e / r for e, r in zip(data.ebitda, data.revenue, strict=True))
    base_revenue = data.revenue[-1]
    latest_nwc = data.nwc[-1] / base_revenue if base_revenue else base["nwc_pct"]
    latest_capex = data.capex[-1] / base_revenue if base_revenue else base["capex_pct"]
    flat_growth = [DEFAULT_TERMINAL_GROWTH] * PROJECTION_YEARS

    scenarios: list[dict[str, Any]] = [
        {"variable": "ebitda_margin", "base_desc": f"latest {base['margins'][0]:.1%}",
         "low": value(margins=[min_margin] * PROJECTION_YEARS),
         "low_desc": f"3yr min {min_margin:.1%}",
         "high": value(margins=[avg_margin] * PROJECTION_YEARS),
         "high_desc": f"3yr avg {avg_margin:.1%}"},
        {"variable": "revenue_growth", "base_desc": f"CAGR decay from {base['growth'][0]:.1%}",
         "low": value(growth=flat_growth), "low_desc": "straight to terminal 3%",
         "high": None, "high_desc": "—"},
        {"variable": "nwc_ratio", "base_desc": f"3yr avg {base['nwc_pct']:.1%}",
         "low": value(nwc_pct=latest_nwc), "low_desc": f"latest yr {latest_nwc:.1%}",
         "high": None, "high_desc": "—"},
        {"variable": "capex_ratio", "base_desc": f"3yr avg {base['capex_pct']:.1%}",
         "low": value(capex_pct=latest_capex), "low_desc": f"latest yr {latest_capex:.1%}",
         "high": None, "high_desc": "—"},
        {"variable": "terminal_growth", "base_desc": "3.0%",
         "low": value(_terminal=0.02), "low_desc": "2.0%",
         "high": value(_terminal=0.035), "high_desc": "3.5%"},
        {"variable": "wacc (via ERP)", "base_desc": f"ERP {DEFAULT_MARKET_PREMIUM:.1%}",
         "low": value(_erp=DEFAULT_MARKET_PREMIUM + 0.01), "low_desc": "ERP +1pp",
         "high": value(_erp=DEFAULT_MARKET_PREMIUM - 0.01), "high_desc": "ERP -1pp"},
        # Beta is the probe that resolved MPC: measured 0.51 -> +84% vs market; stressed
        # to 1.0 -> -1%. A 2-year regression beta on a commodity cyclical carries the
        # whole valuation, so the tornado must show it, not bury it inside WACC.
        {"variable": "beta", "base_desc": f"Blume {beta:.2f} (raw {raw_beta:.2f})",
         "low": value(_beta=raw_beta), "low_desc": f"raw regression {raw_beta:.2f}",
         "high": value(_beta=1.0), "high_desc": "market beta 1.00"},
    ]
    for s in scenarios:
        outputs = [v for v in (s["low"], s["high"]) if v is not None]
        s["swing"] = round(max(abs(v - base_fv) for v in outputs), 2) if outputs else 0.0
    scenarios.sort(key=lambda s: -s["swing"])

    bear = value(margins=[avg_margin] * PROJECTION_YEARS, growth=flat_growth)

    return {
        "symbol": symbol,
        "base_fair_value": base_fv,
        "wacc": base_result["wacc"],
        "tornado": scenarios,
        "bear_composite": bear,
        "bear_composite_desc": "3yr-avg margin + straight-to-terminal growth + 3yr-avg NWC/capex",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--price", type=float, default=None,
                        help="Market price for gap context (optional, avoids a live fetch)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_sensitivity(args.symbol.upper())
    if args.json:
        print(json.dumps(result, indent=2))
        return 1 if result.get("error") else 0
    if result.get("error"):
        print(f"\nDCF sensitivity — {result['symbol']}: {result['error']}")
        return 1

    fv = result["base_fair_value"]
    print(f"\nDCF sensitivity — {result['symbol']}   base ${fv:,.2f}   WACC {result['wacc']:.2%}")
    if args.price:
        print(f"  market ${args.price:,.2f}  ->  base gap {(fv / args.price - 1) * 100:+.0f}%")
    print(f"\n  {'variable':<18}{'scenario':<26}{'fair value':>12}{'vs base':>10}")
    print("  " + "-" * 66)
    for s in result["tornado"]:
        for side in ("low", "high"):
            v = s[side]
            if v is None:
                continue
            print(f"  {s['variable']:<18}{s[side + '_desc']:<26}{v:>11,.2f}{v - fv:>+10,.2f}")
    bear = result["bear_composite"]
    print(f"\n  BEAR COMPOSITE ({result['bear_composite_desc']}):")
    if bear is None:
        print("    refused (assumptions left the valid region)")
    else:
        delta_pct = (bear / fv - 1) * 100
        print(f"    ${bear:,.2f}   ({delta_pct:+.0f}% vs base)")
        if args.price:
            print(f"    vs market ${args.price:,.2f}: {(bear / args.price - 1) * 100:+.0f}%")
    print("\n  MEASUREMENT ONLY — no trades, gate untouched (rule #47).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
