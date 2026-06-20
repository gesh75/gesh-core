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

## Session 3 — 2026-06-20 (tax_harvester + env wiring)

### Shipped ✅

| Module | gesh-core path | Notes |
|---|---|---|
| `tax_harvester` | `gesh_core/tax_harvester.py` | DB path moved off `__file__` to an **env-driven resolver** (`_primary_db()`): `GESH_TRACKER_DB` → `GESH_TRADING_HOME/gesh_financial.db` → `cwd/gesh_financial.db`, resolved at call time. VirtioFS `/tmp` fallback preserved. `generated_at` switched to the non-deprecated `datetime.now(timezone.utc)` form (same output string). |

**Env wiring (the deferral blocker, now closed):**
- Engine: no wiring — its start scripts `cd` to the engine root, so the cwd
  fallback resolves to the engine's `gesh_financial.db` exactly as the old
  `__file__.parent` did.
- Product: exports `GESH_TRACKER_DB` (defaulting to the sibling engine repo's db)
  in both launchd-invoked entry points — `start_gesh_main.sh` (server :9000,
  `/api/tax-harvest`) and `run_daily_analysis.sh` (the 10:30 chain, which `cd`s to
  the product root). Mirrors the existing `proof_page.py`/`progress_view.py`
  `GESH_TRACKER_DB` convention.

- **Tests:** +13 gesh-core parity tests (resolver precedence + scan/wash-sale
  logic, all on a tmp DB via `GESH_TRACKER_DB`). Engine **293 passed**, product
  **143 passed** — zero new failures. Verified product resolves to the engine db
  *with* the wiring env and to its own cwd db *without* (so the wiring is what
  preserves behavior).

## Session 4 — 2026-06-20 (trading.config + trading.state union; tracker NOT extracted)

Investigation reframed this phase: **`tracker`/`metrics`/`tracker_weekly` are
engine-only** (no duplication → no de-drift value, and they're the autonomy-gate
source of truth, rules #26/#44). They were deliberately **not** extracted. The
real shared-but-diverged Tier-3 modules were `config` and `state`.

### Shipped ✅ (union-merged — diverged by feature, not accident)

| Module | gesh-core path | Harmonization |
|---|---|---|
| `trading.config` | `gesh_core/trading/config.py` | Engine's **superset** RiskConfig (extra gates: max_sector_pct, earnings_proximity_hours, max_consecutive_loss_days, min_confidence_risk_off, market_regime_*) + product's empty-string-robust `_env_float/_env_int`. Product gains the extra fields (additive). Ultra-conservative paper defaults asserted in tests. |
| `trading.state` | `gesh_core/trading/state.py` | UNION: engine's WAL/busy_timeout + `job_markers`/`get_marker`/`set_marker` (rule #38) + `count_orders_today(approved_only=)` superset signature; product's `_resolve_db` VirtioFS `/tmp` fallback; and the **two-book** `paper_realized_pnl_usd_today` (paper_outcomes + trade_log paper_trades). Engine's paper_trades is empty (rule #20) so its DAILY_LOSS behavior is unchanged. DB path is cwd/`GESH_DB_PATH` → each repo keeps its OWN gesh_financial.db (separate books, rule #44). |

- **Safety boundary preserved:** paper-mode guard tests green in both repos
  (engine `test_risk_gate_paper_*` + `test_catch_up_on_wake` = 19 passed;
  product `test_risk_gate_paper_mode.py` = 8 passed). Paper-mode defaults
  (PAPER_MODE/REQUIRE_APPROVAL True) asserted explicitly in gesh-core tests.
- **Tests:** +26 gesh-core parity tests (config 16, state 10). Engine **293
  passed**, product **143 passed** — zero new failures.
- **Ends the rule-#40 manual-sync burden** for config/state across the two repos.

## Session 5 — 2026-06-20 (risk_gate: shared seam-free helpers)

`risk_gate` diverges as a **deliberate per-repo gate policy** (engine runs 3 extra
gates — SECTOR_CAP / EARNINGS_PROXIMITY / LOSS_STREAK — and a stricter
MARKET_REGIME). Forcing a single `evaluate()` would change the *other* repo's
production trade approvals, so (per the chosen approach) only the **seam-free
shared primitives** were extracted; each repo keeps its own `evaluate()`.

### Shipped ✅

| New | gesh-core path | What |
|---|---|---|
| `trading.risk_gate_core` | `gesh_core/trading/risk_gate_core.py` | `GateVerdict` (the verdict type execution.py imports in both repos), `_kill_switch_present`, and `_post_trade_cash_estimate` (CASH_FLOOR math, rule #32 — PAPER sizes against cfg.paper_cash_usd, LIVE against real cash). Each repo's `risk_gate.py` now imports these (AST-rewired) and keeps its own `evaluate()`. |

**Why only these three:** the time/PnL-entangled helpers (`_within_market_hours`,
`_quote_age_seconds`, `_daily_pnl_pct`) stay per-repo because the tests freeze each
risk_gate module's `datetime` and patch its `paper_realized_pnl_usd_today` seam —
moving them broke those seams. The underlying P&L computation is already shared via
`state.paper_realized_pnl_usd_today` (Phase 3.4), so the residual drift is minimal.

- **Tests:** +7 gesh-core parity tests (GateVerdict, kill-switch, CASH_FLOOR
  paper-vs-live). `GateVerdict` identity confirmed shared across `risk_gate` and
  `execution` in both repos. Engine **293 passed**, product **143 passed / 7
  pre-existing** — zero new failures. Paper-mode + market-regime guard tests green.

### Backlog (later sessions)

- **`tracker` / `metrics` / `tracker_weekly`:** engine-only by design — NOT
  extraction candidates (no drift; they are the autonomy-gate source of truth).
- **`risk_gate.evaluate()` + the time/PnL helpers:** intentionally per-repo (gate
  policy + test seams). Could be unified later only with a shared injectable clock.
- **`db.py`** (118 diff lines), **`consensus`** (11-node vs 6-node — design
  decision). Need their own analysis.

## Rollback

- Pre-Phase-3 baseline: tag `backup/pre-phase3-2026-06-19` (both repos) +
  `~/Backups/gesh-pre-phase3-2026-06-19.tar.gz`.
- Phase 3.1 checkpoint: tag `backup/post-phase3.1-2026-06-19` (all three repos).
- Phase 3.2 checkpoint: tag `backup/post-phase3.2-2026-06-20` (all three repos).
- Each module is its own commit in all affected repos — revert individually.
