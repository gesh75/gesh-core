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

- **Tier 2:** `ecg` (15-line diff), `kelly` (mergeable price_source fallback),
  `tax_harvester` (DB-path param).
- **Tier 3 / harmonization:** `contract` (decision above), `trading.state` /
  `trading.config` / `trading.tracker` (+ `metrics`), `consensus`
  (11-node vs 6-node — design decision).

## Rollback

- Pre-Phase-3 baseline: tag `backup/pre-phase3-2026-06-19` (both repos) +
  `~/Backups/gesh-pre-phase3-2026-06-19.tar.gz`.
- Each module is its own commit in all affected repos — revert individually.
