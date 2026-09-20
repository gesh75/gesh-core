# Gap analysis — gesh-core

> Merge note (2026-09-19): `main` (`1ed6f16`, through PR #80) was merged into
> this branch. Fail-closed NaN guards from this PR are kept. Since the scan
> below, `main` also landed #65 (parallel gap scan), #77 (R1 allocation
> permission split), #78 (R3 `LedgerUnavailable`), #79 (R6 numeric safety
> config), and #80 (R8 max-drawdown starting equity).

Scanned `56f14d4` (`main` = `ci: raise fd limit before pytest (#46)`).
Date: 2026-09-05. Method: local proofs against installed `src/`, `pytest` +
`ruff` + `mypy` config, `gh` tags/releases/PRs/Actions, tree + test inventory.

This is a scan, not a rewrite. Three fail-closed numeric guards landed in the
same PR; everything else is ranked and left alone.

---

## P0 — fail-open / stale control / unmerged safety work

Each item cites a path and the evidence that made it P0.

### P0-1. Entry floor fails open on NaN / ±Inf raw_score

- **Path:** `src/gesh_core/trading/autopilot_core.py` (`entry_floor_blocks`)
- **Evidence:** `float("nan") < 0.3` is `False` (IEEE-754). On this SHA, before
  the fix in this PR:
  `entry_floor_blocks("BUY", float("nan"), 0.3) is False` — a missing consensus
  number is treated as *above* the floor and a new long is allowed.
  `tests/test_autopilot_core.py` parametrized only finite scores.
- **Fix in this PR:** non-finite `raw_score` / `min_entry_score` now block BUY.
  SELL/HOLD unchanged.

### P0-2. Allocation gate fails open on NaN trade size and NaN cash

- **Path:** `src/gesh_core/allocation_config.py` (`validate_action`)
- **Evidence:** with `auto_trade=True` on this SHA, before the fix:
  `validate_action("BUY", "NVDA", float("nan"), 0, current_cash=100_000)` →
  `(True, "OK")`. Same for `current_cash=float("nan")`. `NaN > cap` and
  `NaN < min_cash_buffer` are both `False`, so the dollar cap and cash floor
  never fire. `inf` was already blocked (`inf > cap`).
  `tests/test_allocation_config.py` had no non-finite size/cash cases.
- **Fix in this PR:** non-finite / non-numeric `trade_usd` (all actions) and
  `current_cash` on BUY/ADD return `(False, "Invalid …")`. SELL/TRIM still
  ignore a dirty cash snapshot so emergency exits are not blocked.

### P0-3. `TradeIntent.validate` accepts NaN / +Inf stops

- **Path:** `src/gesh_core/trading/contract.py` (`TradeIntent.validate`)
- **Evidence:** before the fix,
  `TradeIntent(..., stop_loss=float("nan"), take_profit=float("inf")).validate()`
  returned `[]`. The old check is `stop_loss <= 0`; `NaN <= 0` is `False`.
  `tests/test_contract.py` only covered `-1` / `0`.
- **Fix in this PR:** non-finite stop / take-profit are rejected the same as
  non-positive levels.

### P0-4. Paper daily-loss P&L is UTC-day; order cap is ET-day

- **Path:** `src/gesh_core/trading/state.py`
  - `count_orders_today` (lines ~360–383) uses `America/New_York`.
  - `paper_realized_pnl_usd_today` (lines ~400–413) uses
    `datetime.now(UTC).strftime("%Y-%m-%d")` and documents “since 00:00 UTC today”.
- **Evidence:** the daily-loss breaker (rules #36/#40) and the order-rate cap
  can disagree for the last 4–5 hours of the ET session. Tests pin the UTC
  behaviour (`tests/test_state.py` `_today_iso()`), so CI stays green while the
  two clocks diverge. Draft PR #56 exists; **not fixed here** (needs a
  behaviour decision + test rewrite, not a one-liner).

### P0-5. Sentiment ticker match treats English words as mentions

- **Path:** `src/gesh_core/sentiment_connector.py` (`_is_relevant`, ~181–194)
- **Evidence:** `\b{sym}\b` + `re.IGNORECASE` on this SHA:
  `_is_relevant("I am on the market today", "ON") is True`,
  `_is_relevant("This is a great stock", "A") is True`,
  `_is_relevant("it looks good to me", "IT") is True`.
  `tests/test_sentiment_connector.py` only covers regex escaping, not
  short-ticker / stop-word collisions. Draft PR #62. **Not fixed here**
  (needs a word-list / cashtag policy, not a one-liner).

### P0-6. CASH_FLOOR math returns NaN when live cash is NaN

- **Path:** `src/gesh_core/trading/risk_gate_core.py` (`_post_trade_cash_estimate`)
- **Evidence:** `float(eq_summary.get("cash", 0) or 0)` keeps `NaN`
  (`NaN` is truthy). Proof: estimate with `cash=nan` is `nan`. A downstream
  `post < floor` comparison then fails open. Draft PR #52. **Not fixed here**
  (callers live in the consumer repos; changing the return type is not local).

### P0-7. Control document names the wrong `main` SHA

- **Path:** `PROJECT_CONTROL.md` (header + §8)
- **Evidence:** document claims verified `main` = `97a519b7…` (PR #34, 2026-08-22).
  Live `origin/main` is `56f14d4e…` (PR #46, 2026-08-27). Open-PR / “single next
  action” claims are also stale (27 open draft PRs; see P1-3). This is the same
  class of drift the doc already admitted for 2026-07-31 → 2026-08-22.

---

## P1 — CI, process, coverage, consumers

| ID | Gap | Evidence |
|---|---|---|
| P1-1 | Latest Git tag is still `v0.6.1`; no GitHub Releases; declared version is `0.8.2` | `gh api …/tags` → `v0.6.1` @ `f11c460f`; `…/releases` length `0`; `pyproject.toml` + `__init__.py` = `0.8.2`. README already warns “never pin a tag”. |
| P1-2 | CI coverage is informational — no floor | `.github/workflows/ci.yml` has no `--cov-fail-under`. This SHA: **76%** (`pytest --cov=gesh_core`, 450 passed). Copilot instructions ask for 80%+. Lowest: `dcf/sensitivity.py` 17%, `dcf/inputs.py` 30%, `dcf/__main__.py` 0%, `sentiment_connector.py` 57%. |
| P1-3 | 27 open *draft* PRs (critical-bug + missing-test agents) never merged | `gh pr list --state open` on 2026-09-05. Includes fail-closed work that overlaps P0-2/P0-3/P0-4/P0-5. Process debt, not a code rewrite. |
| P1-4 | Consumer pin freshness unverifiable from this token | `gh api repos/gesh75/Gesh-Project/contents/requirements.txt` and `gesh-project-trading` → 404. `PROJECT_CONTROL.md` last claimed product @ `49312393` (0.8.1, 1 commit behind *then*) and engine @ `33af7482` (0.8.0, 2 behind *then*). Both are now at least PR #46 behind. |
| P1-5 | `htmlcov/` and `.sentiment_cache.json` are not gitignored | `.gitignore` has `.coverage` and `gesh_financial.db` but not the HTML cov tree or the sentiment cache written by `sentiment_connector.py`. |
| P1-6 | Copilot setup workflow pins older Actions than CI | `.github/workflows/copilot-setup-steps.yml` uses `checkout@v4` / `setup-python@v5`; `ci.yml` uses `@v5` / `@v6`. |

---

## P2 — DX, docs, dead / local-only scripts, size

| ID | Gap | Evidence |
|---|---|---|
| P2-1 | No root `LICENSE` / SPDX | Tree has only `src/gesh_core/dcf/vendor/LICENSE-cookbooks`. Owner call (already backlog in `PROJECT_CONTROL.md`). Do not invent. |
| P2-2 | `docs/consensus_parity.py` is a laptop-only harness | Hard-coded `/Users/georgigaydarov/Projects/gesh-project-trading` and `gesh-project`. Broken for anyone else; not invoked by CI. |
| P2-3 | CI import discovery skips `__main__` | `.github/workflows/ci.yml` `if rel.endswith(".__main__"): continue` — `gesh_core.dcf.__main__` is never imported in that step. `python -m gesh_core.dcf` is covered only indirectly. |
| P2-4 | Files over the 400-line copilot guideline | `ledger/integration.py` 618, `trading/state.py` 550, `kelly.py` 544, `sentiment_connector.py` 457. Extract later; do not split in this PR. |
| P2-5 | `PHASE3_STATUS.md` is a 2026-06-20 extraction log | Fine as history; still linked from README as if current. Point readers at `PROJECT_CONTROL.md` / this file. |
| P2-6 | `SENTIMENT_CACHE_FILE` is resolved at import | Same class of bug `CONFIG_PATH` used to have: cwd / env changes after import are ignored. Tests work around it. |
| P2-7 | Broad `except Exception` on network / cache paths | Annotated `# noqa: BLE001` in `market_fetch`, `sentiment_connector`, `kelly`, `dcf`. Intentional fail-soft; leave unless a path should fail closed. |

---

## What this PR changed (3 fixes only)

1. `entry_floor_blocks` — fail closed on non-finite scores.
2. `validate_action` — fail closed on non-finite trade size / cash.
3. `TradeIntent.validate` — fail closed on non-finite stop / take-profit.

No dependency upgrades, no LICENSE invented, no tag cut, no consumer-pin
edits (other repos), no sentiment / timezone / CASH_FLOOR rewrites.

---

## What was proved vs skipped

**Proved**

- IEEE-754 fail-open on the three gates above (interpreter + failing tests
  written first against `56f14d4` behaviour).
- Tag/release gap (`v0.6.1`, zero Releases).
- `PROJECT_CONTROL.md` SHA is two merged commits behind live `main`.
- Sentiment short-ticker false positives; UTC vs ET paper-P&L split;
  CASH_FLOOR NaN estimate (left unfixed; see P0-4/5/6).
- Main CI on `56f14d4` was green (Actions run `33033241239`).
- No root LICENSE; `.gitignore` misses `htmlcov/` and `.sentiment_cache.json`.

**Skipped (on purpose)**

- Large fail-closed draft PRs (#43–#63) — review/merge separately; do not
  re-implement them here.
- Consumer pin bumps — other repositories; API 404 from this token.
- Coverage floor, LICENSE, annotated `v0.8.2` tag — owner / release ritual.
- File splits, sentiment word-list, ET paper-P&L rewrite.

---

## Next recommended agent job

Land P0-4 (ET-day `paper_realized_pnl_usd_today` + rewrite `tests/test_state.py`
clock) *or* triage-merge the oldest green draft fail-closed PRs so 27 drafts
stop rotting — do not open another scan until one of those ships.
