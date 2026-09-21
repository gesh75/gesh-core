# Deterministic DCF — `gesh_core.dcf`

> Measurement only (rule #47). Nothing in this package places trades, writes a
> database, or feeds a risk gate. Verified against `src/gesh_core/dcf/` at
> package **0.8.2** (`main` `a6d287bb`; DCF sources unchanged since the 0.8.2
> characterization tests).

The product's `fair_value_estimate` is an LLM opinion. This package builds an
auditable per-share value from Yahoo statements plus **named** assumptions, so
the two numbers can be compared and a gap traced to a stated input.

## Public API

```python
from gesh_core.dcf import (
    DCFInputs,               # frozen dataclass; monetary figures in $ millions
    fetch_dcf_inputs,        # network: statements → DCFInputs
    compute_fair_value,      # network: statements + profile → result or error dict
    value_with_assumptions,  # pure: DCFInputs + assumptions → EV / equity / WACC
    run_sensitivity,         # network once, then re-value (tornado + bear composite)
)
```

`DCFInputs.available` is `True` only when there is no `error`, `missing` is
empty, at least **3** fiscal periods are present, and `revenue` / `ebitda` /
`capex` / `nwc` are the same length as `years`. Callers must check it — fields
are never filled with plausible defaults.

Error shape from `compute_fair_value`:

```python
{"symbol": "IONQ", "error": "NWC is … of revenue (limit 60%) — …", "fetched": True}
```

`run_sensitivity` returns `{"symbol", "error"}` (no `fetched` key) when the
headline DCF refuses. `value_with_assumptions` is the only path that does **no**
network I/O and returns `{"error": "…"}` without a symbol. Sensitivity reuses
it so every scenario is valued against the same fetched statements.

In-repo characterization tests live in `tests/test_dcf.py` (fetch and profile
are monkeypatched — the suite is network-free).

## CLI (this package)

```bash
python -m gesh_core.dcf --symbol AMD
python -m gesh_core.dcf --symbol AMD --terminal-growth 0.025 --json

python -m gesh_core.dcf.inputs --symbol AMD
python -m gesh_core.dcf.inputs --symbol AMD --periods 5 --json

python -m gesh_core.dcf.fair_value --symbol AMD --risk-free 0.04 --json

python -m gesh_core.dcf.sensitivity --symbol MPC
python -m gesh_core.dcf.sensitivity --symbol MPC --price 150 --json
```

`python -m gesh_core.dcf` is an alias of the fair-value CLI (`dcf/__main__.py`).
`--json` prints the result dict. Process exit status is `1` when the model
refuses or inputs are unavailable.

## What is fetched vs assumed

| Kind | Fields |
|---|---|
| **Fetched** | revenue, EBITDA, capex, operating NWC, tax rate, shares, net debt, sector, raw beta (when Yahoo `info.beta` is in `(0, 5)`) |
| **Assumed (printed every run)** | 5-year revenue-growth path, flat EBITDA margin, terminal growth, risk-free, equity risk premium, cost of debt, D/E |

Default assumption constants (`fair_value.py`):

| Name | Default |
|---|---|
| projection years | 5 |
| terminal growth | 3.0% |
| risk-free | 4.2% |
| market premium (ERP) | 5.5% |
| cost of debt | 4.5% |
| debt / equity | 0.25 |
| beta if profile missing | 1.1 |

Successful `compute_fair_value` results also disclose `capex_pct` and `nwc_pct`
on both `inputs_fetched` and `assumptions` (v0.8.2).

## Methodology (v0.8.0 revision)

Practitioner review (2026-08-08) changed the headline case. Do not treat a
pre-0.8.0 number as comparable without re-running.

1. **Operating NWC, not headline current assets − liabilities.** Cash / short-term
   investments and short-term debt are excluded (financing, not operations).
   Absent cash or ST-debt rows subtract as `0`. Series are keyed by statement
   **date**, then intersected across income / cash-flow / balance-sheet frames
   so a gap in one statement cannot pair the wrong fiscal years.

2. **Capex and NWC ratios are multi-year averages** of `value / revenue` over
   **positive-revenue** years only. Zero-revenue years are skipped, not treated
   as a 0% ratio. If no positive-revenue period remains, `_avg_ratio` raises
   and `compute_fair_value` returns that as a named error (v0.8.2 / PR #35).
   Latest-year ratios are a sensitivity scenario, not the base.

3. **EBITDA margin** is still the **latest** year, held flat for five years.

4. **Revenue growth** decays historical CAGR toward terminal growth. The
   extrapolated start is clamped to `[terminal, 60%]`. Horizons of 0 or 1 year
   return the terminal rate (no divide-by-zero).

5. **Blume beta** when Yahoo supplies a usable raw beta:
   `0.67 * raw + 0.33 * 1.0`. Raw and adjusted are both reported.
   `compute_fair_value` also values once at market beta `1.0`; if that swing
   exceeds **25%**, `beta_sensitivity.fragile` is `True`.

6. **Opening NWC seed.** Upstream `DCFModel.project_cash_flows` hardcodes
   `prev_nwc = base_revenue * 0.10`. GESH overrides that in `_SeededDCFModel`
   using the last historical NWC so a high-NWC name does not invent a year-1
   working-capital shock. The vendored file stays byte-identical to upstream.

## Refusal guards (fail closed)

The model returns an error dict rather than a negative or meaningless price:

| Guard | Threshold / rule |
|---|---|
| Missing / empty statements | `available=False`, `fetched=False` — nothing invented |
| Sector | `Financial Services`, `Financials` — comparison is **case-insensitive** after strip; NOPAT / % of revenue does not apply to customer-funds or lending books |
| EBITDA margin | latest year `< 5%` — pre-scale FCF is not meaningful |
| Empty ratio base | no positive-revenue periods — percent-of-revenue DCF is undefined |
| Any non-positive revenue | `value_with_assumptions` refuses the whole series (it does not skip a zero year) |
| NWC / revenue | average `> 60%` — % of revenue projection is invalid |
| Capex / revenue | average `> 35%` — not a sustainable perpetuity assumption |
| Gordon identity | `terminal_growth >= WACC` — infinite value |
| Sign | `fair_value_per_share <= 0` after a successful solve |

Corporate VPN SNI-blocks of Yahoo hosts are an expected failure mode (rule #54).

## Sensitivity (`run_sensitivity`)

Calls `compute_fair_value` first (so a refusal short-circuits), then re-fetches
statements once and perturbs one variable at a time (tornado) plus a **bear
composite** (3-year average margin + straight-to-terminal growth + the
already-average NWC/capex base). Tornado variables:

- EBITDA margin (3y min / 3y avg vs latest-year base)
- revenue growth (straight to 3% terminal)
- NWC ratio and capex ratio (latest year vs 3y-avg base)
- terminal growth (2.0% / 3.5%)
- WACC via ERP (±1pp)
- beta (raw regression / market 1.00 vs Blume)

Scenarios are ranked by absolute swing vs the headline fair value.
`sensitivity._base_assumptions` is kept in lockstep with `compute_fair_value`
by `test_base_assumptions_lockstep_with_compute_fair_value`.

## Vendor and packaging

`dcf/vendor/dcf_model.py` and `sensitivity_analysis.py` are unmodified copies of
[anthropics/claude-cookbooks](https://github.com/anthropics/claude-cookbooks)
(`skills/custom_skills/creating-financial-models/`), MIT, vendored at
`f65eb122a51e9710d4db3f4893016879c65c77d6`. See `dcf/vendor/NOTICE.md`.

GESH-specific corrections belong in `fair_value.py` / `sensitivity.py`, not in
the vendored files. The wheel **must** ship `NOTICE.md` and `LICENSE-cookbooks`
(`pyproject.toml` `[tool.setuptools.package-data]`) — that is the 0.8.1
packaging fix.

Known upstream quirks (do not "fix" in vendor): tornado divides by
`base_output` (zero base raises); advertised Monte Carlo is not implemented
there.

## Constraints and pitfalls

- **Not a trading input.** `fair_value.py` states it is not wired to the :9000
  product and does not move gates. Do not treat a DCF printout as an execution
  signal.
- **OpenBB is not used here.** Comments name it as the repo's preferred
  fundamentals source; it is not a package dependency. yfinance is the real path.
- **Units.** Statement figures are millions USD; `shares_outstanding` is
  millions of shares.
- **Beta fetch is separate** from statement fetch (`yf.Ticker.info`). A
  successful statement pull can still use `DEFAULT_BETA` and set
  `beta_fetched=False`.
- **CLI surface is narrower than the library.** The fair-value CLI exposes
  `--terminal-growth` and `--risk-free` only; ERP, cost of debt, and D/E are
  library / default constants.

## Example (library)

```python
from gesh_core.dcf import compute_fair_value, run_sensitivity

result = compute_fair_value("AMD")
if result.get("error"):
    raise SystemExit(result["error"])

print(result["fair_value_per_share"], result["wacc"], result["assumptions"])
if (result.get("beta_sensitivity") or {}).get("fragile"):
    print("headline is beta-fragile", result["beta_sensitivity"])

tornado = run_sensitivity("AMD")
print(tornado["bear_composite"], tornado["tornado"][0]["variable"])
```
