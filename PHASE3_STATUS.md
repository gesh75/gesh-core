# Phase 3 — gesh-core Extraction Status

De-duplicate the engine (`gesh-project-trading`) and product (`gesh-project`)
repos by moving shared modules into one installable `gesh-core` package. Each
consumer keeps a thin transparent shim where the module used to live, so import
paths stay unchanged.

## Session 1 — 2026-06-19 (Scaffold + Tier 1)

### Shipped ✅

| Module | gesh-core path | Notes |
|---|---|---|
| `allocation_config` | `gesh_core/allocation_config.py` | Was byte-identical across repos. Config path made cwd-relative (`GESH_CONFIG_PATH` override) so each repo keeps its OWN `gesh_config.json`. |
| `trading.indicators` | `gesh_core/trading/indicators.py` | Pure numpy ATR helper. Extracted because `levels` depends on it. |
| `trading.levels` | `gesh_core/trading/levels.py` | Stop/target derivation. Optional `from consensus import …` still resolves in the engine, degrades to flat stops elsewhere. |

- **Package:** src-layout, `pip install -e ../gesh-core` wired into both repos'
  venvs + `requirements.txt`.
- **Shim pattern:** transparent `sys.modules[__name__] = _impl` alias — preserves
  every import form (`from x import y`, `import x as z`, underscore names,
  relative `from .levels import …`) AND monkeypatching (patches hit the single
  shared namespace, so internal calls see them).
- **Tests:** engine suite **293 passed** before and after every module.
  gesh-core has 14 own parity tests. Engine `test_gesh_core_candidates.py`,
  `test_atr_stops.py`, `test_atr_resilience.py`, `test_phase1_fixes.py` all green
  through the shims.
- **De-drift proof:** both repos resolve these modules to the identical files
  under `~/Projects/gesh-core/src/gesh_core/` — drift is now structurally impossible.

### Deferred (verified, with reason) ⏭️

The prior audit's "4 safest" list was optimistic; two candidates are not clean
Tier-1 relocations:

| Module | Why deferred | Unblock |
|---|---|---|
| `trading.contract` | **DIVERGED**, not identical. Engine's `manual()` has a `source=` provenance param (2026-06-14 fix) + a `len(symbol) > 12` validation cap that product lacks. Choosing a canonical version is a harmonization decision (out of session scope). | Adopt engine version as canonical superset (product callers stay compatible — `source` defaults to `"manual"`); accept product's minor stricter symbol validation. Run BOTH repos' contract tests. |
| `trading.metrics` | **Coupled to `tracker`** (Tier 3). Imports `from .tracker import _conn, LAUNCH_DATE, MIN_AGREEMENT_N, _utc_now`. Moving it alone breaks `_conn` resolution → autonomy gate. | Extract `tracker` (+ its DB schema) first, or invert the dependency so the DB connection is injected. |

### Backlog (later sessions)

- **Tier 3 / structural:** `trading.state` / `trading.config` / `trading.tracker`
  (+ `metrics`, which is tracker-coupled), `consensus` (11-node vs 6-node — design
  decision).

## Session 2 — 2026-06-20 (Tier 2 harmonization)

GitHub: pushed to **https://github.com/gesh75/gesh-core** (private) at start of session.

### Shipped ✅ (each harmonized — diverged, picked/merged a canonical version)

| Module | gesh-core path | Harmonization decision |
|---|---|---|
| `trading.contract` | `gesh_core/trading/contract.py` | **Union of both:** engine's `manual(source=…)` provenance param (2026-06-14 fix) + product's stricter `len(symbol) > 12` cap. Product callers unchanged (`source` defaults to `"manual"`). |
| `ecg` | `gesh_core/ecg.py` | **Product canonical** (the fixed version): `compute_ecg` derives loss streaks from consecutive equity CHANGES, not the percent_change-vs-cost column that falsely SUSPENDed underwater holdings. Engine gains the fix. Helpers were already identical. |
| `kelly` | `gesh_core/kelly.py` | **Union:** engine's rule-#43-hardened fetch (Yahoo 2y + Robinhood fallback, avoids "possibly delisted" on rebranded crypto tickers) + product's injectable `returns=` param (network-free unit tests). |

- **Tests:** +52 gesh-core parity tests (contract 19, ecg 20, kelly 13). Engine
  **286 passed**, product **143 passed** after every module — zero new failures.
- **Known environmental noise:** the engine's 7 `test_risk_gate_market_regime`
  failures are the weekday-gated MARKET_HOURS tests (`risk_gate.py` rejects on
  Sat/Sun) — they fail only because this session ran on a **Saturday**; verified
  by reproducing them with the shim stashed. Product's 7 pre-existing failures
  (2 ai_analyzer caching, 2 consensus tally, 1 price_source network, 2 risk_gate
  sandbox-SPY) are unchanged from baseline (AUDIT_GUIDE §5).

### Deferred (verified, with reason) ⏭️

| Module | Why deferred | Unblock |
|---|---|---|
| `tax_harvester` | Only real divergence is the **DB-path default**: product reads the *engine's* `gesh_financial.db` via a sibling-path default, and `GESH_TRACKER_DB` is set nowhere in product's runtime. A single shared default needs env wiring across product's launchd plists + server start script. | Set `GESH_TRACKER_DB` for all product entry points, then canonical can default to `cwd`/env. |

### Backlog (later sessions)

- **Tier 3 / structural:** `trading.state` / `trading.config` / `trading.tracker`
  (+ `metrics`), `consensus` (design decision). These need a unified DB schema /
  dependency inversion before extraction.
- **tax_harvester** env wiring (above).

## Rollback

- Pre-Phase-3 baseline: tag `backup/pre-phase3-2026-06-19` (both repos) +
  `~/Backups/gesh-pre-phase3-2026-06-19.tar.gz`.
- Phase 3.1 checkpoint: tag `backup/post-phase3.1-2026-06-19` (all three repos).
- Phase 3.2 checkpoint: tag `backup/post-phase3.2-2026-06-20` (all three repos).
- Each module is its own commit in all affected repos — revert individually.
