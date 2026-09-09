# gesh-core gap analysis

Scan date: **2026-09-05**. Tree: branch `cursor/gap-scan-gesh-core-9a8a` off `main` `56f14d4e3a8fd527a9637cc7fb1ce2042c11aee0` (`ci: raise fd limit before pytest (#46)`).

This is a **verifiable** scan: every P0 has a file path plus a reproduced failing check, missing test, secret smell, or broken script. No large rewrites. Three small fail-closed patches landed in this PR; everything else is left for a later job.

## Method

| Check | Result |
|---|---|
| `pip install -e '.[dev]'` | OK |
| `ruff check src tests` | clean (post-fix) |
| `mypy src` | clean (post-fix) |
| `pytest -q` | green (post-fix; was 442 passed on `main`) |
| CI import-all-modules (`ci.yml` filesystem walk) | 30 non-vendor modules |
| GitHub Actions on `main` | success, run `33033241239` |
| This PR required GHA (`lint` + test 3.12/3.13/3.14) | success, run `33942411302` |
| Buildkite `CI (pull_request)` on this PR | **failed** — importer path-filter eval, not pytest (P1-15) |
| Latest Git tag | `v0.6.1` (no `v0.7` / `v0.8`) |
| GitHub Releases | **none** (`gh api …/releases` → `0`) |
| Root `LICENSE` | **missing** |

Open draft PRs already targeting some of these gaps (`#54` NaN stops, `#60` NaN trade sizes, `#62` sentiment ticker words, `#63` leftover characterization tests). They are **not merged**; the bugs below are still on `main`.

---

## P0 — fail-closed / broken / secret-adjacent

### P0-1. `kelly._fetch_returns` discovers `price_source` via `sys.path`

**File:** `src/gesh_core/kelly.py` (was L154–155)  
**Sibling already hardened:** `src/gesh_core/market_fetch.py` L72–81 + `tests/test_market_fetch.py` `test_download_does_not_import_untrusted_fallback`

**Evidence (reproduced 2026-09-05):** planted `tmp/price_source.py` that touches a marker, stubbed Yahoo to empty, called `_fetch_returns("NVDA")` → **marker created**. Same fixture against `yf_download_with_retry` does **not** create the marker.

**Why it matters:** cwd is first on `sys.path`. On the Yahoo 401/crumb path this installed library executed whoever’s `price_source.py` was first. Hosts that already imported their real module are fine; every other caller is not.

**This PR:** only call `sys.modules.get("price_source")` (host already imported). New tests: `test_fetch_returns_does_not_import_untrusted_price_source`, `test_fetch_returns_uses_already_imported_host_price_source`.

### P0-2. `docs/consensus_parity.py` is not runnable from a clean checkout

**File:** `docs/consensus_parity.py` L3–4  
**Cited as done:** `docs/CONSENSUS_CONVERGENCE.md` L50 (“6/6 symbols within ±0.05”)

**Evidence:**

```
ENG="/Users/georgigaydarov/Projects/gesh-project-trading"
PRD="/Users/georgigaydarov/Projects/gesh-project"
```

Ran from this checkout: exit 0, every symbol `ERR` (`? None`). Hard-coded macOS sibling venvs; neither consumer repo is in this workspace.

**Not fixed here** (needs env-var paths or a move into the consumer repos; do not fake a parity result).

### P0-3. `validate_action` fail-opens on NaN / −inf / negative `trade_usd`

**File:** `src/gesh_core/allocation_config.py` L249–269  
**Missing test:** `tests/test_allocation_config.py` covers caps and bad *actions*, not non-finite money.

**Evidence (reproduced):** with `auto_trade=True`, `validate_action("BUY", "NVDA", nan|-inf|-1.0, 0, current_cash=100_000)` returned `(True, "OK")`. In IEEE floats `nan > cap` and `-1 > cap` are both `False`.

**Not fixed here** — draft PR `#60` already owns this change. Still a live P0 on `main`.

---

## P1 — correctness / CI / security / missing tests

### Correctness

| ID | Gap | Evidence |
|---|---|---|
| P1-1 | Entry-conviction floor fail-opens on NaN/`inf` `raw_score` | `src/gesh_core/trading/autopilot_core.py` (was L35): `raw_score < min_entry_score` is False for NaN. `entry_floor_blocks("BUY", nan, 0.35) is False`. ECG already names this class of bug (`ecg.py` L89–91). **Fixed in this PR.** |
| P1-2 | `KELLY_MAX_GROSS_PCT` not clamped; sibling cap is | `src/gesh_core/kelly.py` `_max_gross_exposure` used raw `float()`. `KELLY_MAX_GROSS_PCT=inf\|nan\|100` → `inf` / `nan` / `100.0`; overbet overlay never scales. `_parse_position_cap` already exists. **Fixed in this PR.** |
| P1-3 | `TradeIntent` / ATR levels accept NaN stops | Draft PR `#54`. `not nan` and `nan <= 0` are False; NaN stops persist into `paper_stops`. |
| P1-4 | Sentiment `_is_relevant` matches English-word tickers | Draft PR `#62`. `\bON\b` / `\bCOST\b` pull whole-subreddit mood into consensus. |
| P1-5 | Risk numeric env parser accepts `inf` / `nan` / unbounded percents | `src/gesh_core/trading/config.py` L20–29. `MAX_DAILY_LOSS_PCT=inf` → daily-loss breaker never trips (`-0.05 < -inf` is False). |
| P1-6 | Public ledger `record_analysis_decision` persists secret-named fields | Adapter strips (`ledger/adapters/daily_analysis.py` L124–145); `ledger/integration.py` dumps raw JSON. Adapter-only test: `tests/test_ledger_daily_adapter.py` L224–240. |
| P1-7 | `dcf.inputs.fetch_dcf_inputs` / `dcf.sensitivity.run_sensitivity` have almost no behavioral tests | Coverage on `main`: inputs ~30%, sensitivity ~17%. `tests/test_dcf.py` monkeypatches fetch; `_base_assumptions` only for sensitivity. |

### CI

| ID | Gap | Evidence |
|---|---|---|
| P1-8 | Coverage is informational; no floor | `.github/workflows/ci.yml` L93: `--cov=gesh_core` with no `--cov-fail-under`. `CHANGELOG.md` L28: “informational, no floor yet”. Copilot asks for 80%+ (`.github/copilot-instructions.md` L29); suite is ~75%. |
| P1-9 | Copilot setup diverges from CI | `copilot-setup-steps.yml`: `checkout@v4`, `setup-python@v5`, `pip install -e '.[dev]'`, no ruff/mypy/pytest. `ci.yml`: `@v5`/`@v6`, `".[test]"`, ruff + mypy + pytest. |
| P1-10 | `ruff format` not gated | `ci.yml` L36 is `ruff check` only. `ruff format --check src tests` exits 1 (32 files). Do **not** mass-format in this PR. |
| P1-15 | Buildkite GHA importer fails this PR independently of GitHub-hosted CI | Required jobs on this PR (`lint`, `test` 3.12/3.13/3.14) succeeded (Actions run `33942411302`). Buildkite check `CI (pull_request)` failed: *“Pull_request trigger path filters could not be evaluated safely”* / *“event snapshot requires full lowercase payload.pull_request base, head, and merge commit SHAs”*. `.github/workflows/ci.yml` has **no** `paths:` filter. Same importer previously needed `ulimit -n` (`56f14d4`, #46). Not a test failure. |

### Security / DX / docs (P1)

| ID | Gap | Evidence |
|---|---|---|
| P1-11 | Control doc SHA is stale | `PROJECT_CONTROL.md` L12: verified `main` = `97a519b7` (pre-0.8.2). Live `main` is `56f14d4`. CI cite L141–142 is run `31493540985`. |
| P1-12 | HTML dashboards still say v0.1.0 / 11 modules / 121 tests | `docs/index.html` L43–48; `docs/architecture.html` same era. Reality: **0.8.2**, ~20 shared modules, **442** tests. |
| P1-13 | Cited profitability memo is missing | `src/gesh_core/trading/config.py` L133 and `levels.py` L36–37 cite `docs/SIGNAL_PROFITABILITY_2026-06.md`. File does not exist. |
| P1-14 | `.gitignore` misses tool caches | `.mypy_cache/` and `.ruff_cache/` are created by local gates and are not ignored. |

---

## P2 — polish / backlog / dead code

| ID | Gap | Evidence |
|---|---|---|
| P2-1 | No Git tag / Release past `v0.6.1` | `gh api repos/gesh75/gesh-core/tags`; Releases length 0. Tag-followers install 0.6.1. Owner-only (never move tags). |
| P2-2 | No root LICENSE / SPDX | Tree has only `src/gesh_core/dcf/vendor/LICENSE-cookbooks`. `pyproject.toml` `[project]` has no `license`. Already backlog in `PROJECT_CONTROL.md` L103 — **do not invent**. |
| P2-3 | Consumer pins lag (external) | Control doc L80–81: product on `49312393` (v0.8.1), engine on `33af7482` (v0.8.0). Not verifiable from this repo alone. |
| P2-4 | Vendored `dcf/vendor/sensitivity_analysis.py` is unused at runtime | Zero imports of that module. Local logic is `dcf/sensitivity.py`. Kept for MIT vendor bundle (`NOTICE.md`) — do not delete without a legal pass. |
| P2-5 | Files over the 400-line Copilot guideline | `ledger/integration.py` 618, `trading/state.py` 550, `kelly.py` 544. Extract later; not a rewrite. |
| P2-6 | No `CODEOWNERS`, Dependabot, pre-commit | Hygiene only. |
| P2-7 | `PHASE3_STATUS.md` test counts are historical | “~121 parity tests” was true at Phase 3 close; suite is now 442. Leave as a session log. |
| P2-8 | Secret denylist misses `client_secret` | `ledger/canonical.py` L30–42 vs this package’s `REDDIT_CLIENT_SECRET`. |

---

## What this PR changed (≤3 small fixes)

1. **Kelly fetch:** do not import untrusted `price_source` (P0-1).
2. **Kelly gross cap:** reuse `_parse_position_cap` for `KELLY_MAX_GROSS_PCT` (P1-2).
3. **Entry floor:** treat non-finite scores as blocked (P1-1).

No dependency upgrades, no LICENSE invented, no HTML rewrite, no coverage floor, no format-all.

## What was skipped (deliberately)

- Allocation NaN / TradeIntent NaN / sentiment English-word tickers — owned by open draft PRs `#60`, `#54`, `#62`.
- Parity harness path rewrite, control-doc SHA bump, HTML dashboard refresh, coverage floor, `ruff format --check`.
- Root LICENSE, tags/releases, consumer pin bumps (owner / other repos).

## Next recommended agent job

Merge or re-land the existing fail-closed drafts (`#54`, `#60`, `#62`) on `main`, then add a network-free `validate_action` NaN/negative characterization test if `#60` does not already include one.
