# gesh-core — Project Control

> Canonical control document for this repository. Linked from [README.md](README.md).
> **This-repo facts re-verified 2026-09-21 against live GitHub.** Consumer pins
> last live-verified 2026-08-22 (those repos 404 from this environment).

## Control header

| Field | Value |
|---|---|
| Repository | `gesh75/gesh-core` |
| Remote | `https://github.com/gesh75/gesh-core.git` (private) |
| Verified `main` | `a6d287bbb146add4d21523c9c9bffdfb6b3cfc8a` (PR #88) |
| Verification timestamp | 2026-09-21, GitHub API against the live remote |
| Declared version on `main` | `0.8.2` (`pyproject.toml` and `__init__.py` agree). Unreleased fail-closed + overlay work is already on `main` under that same version string. |
| Latest release tag | `v0.6.1` → peeled commit `f11c460f…` (**no tags for 0.7.0 / 0.8.0 / 0.8.1 / 0.8.2**) |
| GitHub Releases | **none** |
| Open PRs | many drafts (coverage / bug / stale docs #57 and #71). This docs pass supersedes #57/#71. |
| Runtime | none — this is a library; it has no service, scheduler or database of its own |
| Last completed milestone | **PR #88** `feat(trading): precision_overlay_blocks` (merged as `a6d287bb`) |
| Single next action | **Bump both consumer pins** to a current `main` SHA (see §3). Then cut an annotated tag + GitHub Release so tag-followers stop installing 0.6.1. |

## 1. Current truth

The strict safety-boolean contract remains in force.

`PAPER_MODE`, `REQUIRE_APPROVAL` and `MARKET_REGIME_GATE` are parsed by
`gesh_core.trading.config`:

| Input | Result |
|---|---|
| variable absent | documented conservative default (all three `True`) |
| `true` / `false`, any case, after `.strip()` | accepted |
| blank / whitespace-only | `ConfigError` |
| `1`, `0`, `yes`, `no`, `y`, `n`, `on`, `off` | `ConfigError` |
| any other token | `ConfigError` |

Guarantees:

- **Invalid input is never silently coerced to `False`.**
- Both public paths fail closed — `load_risk_config()` **and**
  `effective_config()` raise; neither returns a usable fallback.
- Raw environment values never appear in metadata or exception messages
  (`<missing>` / `<redacted>` only).
- `effective_config()` returns an immutable settings mapping and a deterministic
  `config_hash` over *name · source · parsed value · validation status* for the
  three variables, with `resolved_at` excluded from the hash.

DCF (v0.7.0/v0.8.0) is measurement-only (rule #47). v0.8.2 adds the first
in-repo characterization tests and discloses `capex_pct` / `nwc_pct` on every
successful result.

Post-0.8.2 on `main` (still declared 0.8.2): allocation permission split
(`require_live_permission`, PR #77), `LedgerUnavailable` (PR #78),
`NUMERIC_SPECS` reject NaN/inf (PR #79), Kelly drawdown includes starting
equity (PR #80), `resolve_db_path` is I/O-free (PR #81), fail-closed NaN
guards (PR #64), and `precision_overlay_blocks` (PR #88). See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## 2. Architecture

Pure library. No service, port, scheduler or datastore.

```
src/gesh_core/
  trading/     config.py  contract.py  indicators.py  levels.py
               state.py  risk_gate_core.py  autopilot_core.py
  dcf/         fair_value.py  inputs.py  sensitivity.py  vendor/
  ledger/      canonical.py  hashes.py  schema.py  repository.py
               integration.py  adapters/daily_analysis.py
  kelly.py  ecg.py  db.py  db_path.py  market_fetch.py
  tax_harvester.py  allocation_config.py  sentiment_connector.py
```

Trust boundary: consumers import `gesh_core.*` directly, and both product repos
alias their local modules onto it via `sys.modules[__name__] = _impl`,
so **every module-level name here is reachable as `trading.config.X` downstream**.

## 3. Consumers and their pins — GitHub-verified 2026-08-22 (not re-checked)

This environment still gets HTTP 404 on `gesh75/Gesh-Project` and
`gesh75/gesh-project-trading`. Figures below are the last successful live
read (2026-08-22). Re-verify before bumping.

| Consumer | Pin | Form | Status |
|---|---|---|---|
| `gesh75/Gesh-Project` | `493123938a173d890c63655ea20410501bd8b9f0` (`v0.8.1`) | 40-char commit ✅ | 🟡 **1 commit behind `main`** — missing PR #34 (unhashable allocation actions). `requirements.txt` |
| `gesh75/gesh-project-trading` | `33af7482c01b4950cab82ba5167e47146f048575` (`v0.8.0`) | 40-char commit ✅ | 🟡 **2 commits behind `main`** — missing v0.8.1 (vendor LICENSE in the wheel) **and** PR #34 |

The 2026-07-31 claim that trading still pinned symbolic tag `v0.4.0` is **obsolete**.
Both consumers pin SHAs. The remaining risk is **lag**, not tag-following.

Bump **both** pins to a current `main` SHA (`a6d287bb` or later). The 2026-08-22
read had trading on `33af7482` (v0.8.0) — that pin misses vendor LICENSE in the
wheel, unhashable-action rejection, DCF tests, and the entire Unreleased
fail-closed / overlay batch. Do not invent a newer consumer SHA from this run.

## 4. Milestones

| State | Item | Exit gate |
|---|---|---|
| ✅ DONE | P0-B strict safety booleans (PR #8) | merged; CI green on 3.12/3.13/3.14 |
| ✅ DONE | `EffectiveConfig` identity + 0.6.2 (PR #11) | merged as `a9342c08` |
| ✅ DONE | Decision ledger Phase 4A | schema + hash contracts + tenant isolation |
| ✅ DONE | `gesh_core.dcf` v0.7.0 / methodology v0.8.0 / wheel LICENSE v0.8.1 | PRs #31–#33 |
| ✅ DONE | Fail-closed hardening batch (PRs #12–#30, #34) | allocation, kelly, ledger, tax, ECG, ATR, CI token |
| ✅ DONE | 0.8.2 DCF tests + CI import discovery | merged; `main` later moved through PRs #64/#77–#81/#88 |
| 🟡 ACTIVE | Docs refresh to `a6d287bb` (DCF page, env catalog, overlay) | this revision |
| ⬜ NEXT | Consumer pin bump (product + engine) to a current `main` SHA | dedicated PRs in those repos; last pin read 2026-08-22 |
| ⬜ NEXT | Annotated tag past `v0.6.1` + GitHub Release | so tag-followers stop at 0.6.1 |
| ⬜ BACKLOG | Root LICENSE file (legal decision — not invented here) | owner call |
| ⬜ BACKLOG | Split files over the 400-line copilot guideline (`ledger/integration` 618, `state` 565, `kelly` 550) | non-breaking extract |

## 5. Achievements (since last control refresh)

- **PR #88 — precision overlay.** `precision_overlay_blocks` / `OverlayDecision` second-stage BUY veto.
- **PRs #77–#81 — fail-closed ops contract.** Allocation caps run with `auto_trade` off; missing paper books raise `LedgerUnavailable`; numeric safety specs reject NaN/inf; Kelly drawdown includes starting equity; `resolve_db_path` is path-only.
- **PR #64 — NaN guards.** Entry floor, trade size/cash, and `TradeIntent` stops fail closed on non-finite values.
- **PR #34 — unhashable trade actions.** Allocation gate rejects non-hashable actions fail-closed.
- **PR #33 — vendor LICENSE in the wheel.** MIT attribution travels with the installed package.
- **PR #32 — DCF methodology.** Operating NWC, Blume beta + fragility, average-ratio base, named refusals.
- **PR #31 — `gesh_core.dcf`.** Shared deterministic valuation, measurement-only.
- **PRs #12–#30 — fail-closed pass.** Wash-sale `/tmp` fallback removed, snapshot hash validation, nested-secret strip, Kelly haircuts, source spoofing, ATR amplification bound, ECG NaN, CI token lockdown.

## 6. Blockers and risks

| Sev | Item | Evidence | Unblock condition |
|---|---|---|---|
| HIGH | No Git tag / Release past `v0.6.1` | `gh api repos/gesh75/gesh-core/tags`; Releases list empty | cut a tag on a chosen `main` SHA; never move tags |
| HIGH | Engine pin last seen two commits behind 0.8.1-era `main` | 2026-08-22 read: `33af7482` (v0.8.0); not re-checked (404) | re-verify then bump to current SHA; run engine suite |
| MEDIUM | Product pin last seen one commit behind 0.8.1-era `main` | 2026-08-22 read: `49312393` (v0.8.1); not re-checked (404) | re-verify then bump to current SHA |
| MEDIUM | Declared version still `0.8.2` after Unreleased landings | `__version__` / `pyproject.toml` | version bump is an owner call, not invented here |
| MEDIUM | Control docs lagged from 2026-08-22 through 2026-09-21 | header still said `97a519b7` / "open PRs none" | this revision |
| LOW | No root LICENSE | tree has only `dcf/vendor/LICENSE-cookbooks` | owner decides SPDX; do not invent |
| LOW | CI import list was a stale allow-list | omitted dcf/ledger/sentiment/market_fetch/autopilot | filesystem discovery (0.8.2) |
| LOW | Copilot 400-line guideline exceeded | `ledger/integration.py` 618, `state.py` 565, `kelly.py` 550, `allocation_config.py` 535 | extract, don't rewrite |

## 7. Execution queue

1. Land this docs refresh (DCF page, env catalog, overlay / fail-closed contract).
2. Re-verify consumer pins (those repos 404 here) and bump both to a current `main` SHA.
3. Cut an annotated tag past `v0.6.1` and a GitHub Release. Pin-by-SHA remains the rule.
4. Decide whether to bump the declared version off `0.8.2` now that Unreleased work is on `main`.
5. Decide a root LICENSE. Until then the package has no SPDX identifier.

**One writer per repository at a time.**

## 8. Verification evidence

| Claim | Evidence |
|---|---|
| `main` = `a6d287bb` | GitHub commits API, 2026-09-21 |
| CI green on that head | Actions run `35547132758`, `head_sha=a6d287bb`, conclusion `success` |
| Product pin (stale read) | 2026-08-22: `Gesh-Project/requirements.txt` → `49312393`; 404 this run |
| Engine pin (stale read) | 2026-08-22: `gesh-project-trading/requirements.txt` → `33af7482`; 404 this run |
| Latest tag is `v0.6.1` | `list_tags`; no `v0.7` / `v0.8` |
| No GitHub Releases | `list_releases` empty |
| In-repo tests | 426 `test_*` functions across 44 files |

## 9. Definition of done

A change is done when: merged to `main`; CI green on the **exact** head SHA;
verified in a disposable checkout where a database or runtime is involved;
consumers' pins and control documents updated; and the runtime/deploy decision
recorded explicitly — including when the decision is "no deployment".

## Change log

| Date | Change | Not changed |
|---|---|---|
| 2026-09-21 | Control header + inventory to `a6d287bb` (PR #88); DCF page / env catalog / overlay + fail-closed contract documented | no consumer pin changed *by this repo* (404); no version bump; no LICENSE invented; no tag cut |
| 2026-08-22 | 0.8.2: DCF tests + fail-closed empty-ratio/zero-revenue + disclosed capex/nwc; CI import discovery; this document rewritten against live GitHub | no consumer pin changed *by this repo*; no runtime; no LICENSE invented |
| 2026-08-11 | PR #34 merged (`97a519b7`): reject unhashable trade actions | docs not refreshed (this gap) |
| 2026-08-08 | PRs #31–#33: DCF module, methodology, vendor LICENSE in wheel (0.7.0 → 0.8.1) | no tag/release cut |
| 2026-07-31 | PR #11 merged (`a9342c08`): `EffectiveConfig` hashable, version `0.6.2` | no consumer pin changed by this repo |
