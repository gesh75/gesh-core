# gesh-core — Project Control

> Canonical control document for this repository. Linked from [README.md](README.md).
> **Verified 2026-09-07 against live GitHub** for this repo. Consumer-pin
> claims that could not be re-fetched are labelled as such.

## Control header

| Field | Value |
|---|---|
| Repository | `gesh75/gesh-core` |
| Remote | `https://github.com/gesh75/gesh-core.git` (private) |
| Verified `main` | `56f14d4e3a8fd527a9637cc7fb1ce2042c11aee0` |
| Verification timestamp | 2026-09-07, GitHub API against the live remote |
| Declared version on `main` | `0.8.2` (`pyproject.toml` and `__init__.py` agree) |
| Latest release tag | `v0.6.1` → peeled commit `f11c460f628fea484c739b6ab25ea0e12c0c8f85` (**no tags for 0.7.0 / 0.8.0 / 0.8.1 / 0.8.2**) |
| GitHub Releases | **none** |
| Open PRs | 34 open (32 drafts): coverage + fail-closed automations + stale docs PRs **#37** and **#57**. No issues queried. |
| Runtime | none — this is a library; it has no service, scheduler or database of its own |
| Last completed milestone | **PR #46** `ci: raise fd limit before pytest` (merged as `56f14d4e`, after 0.8.2 / PR #35). `main` unchanged since 2026-08-27. |
| Single next action | **Bump both consumer pins to `56f14d4e`** (see §3). Then cut an annotated `v0.8.2` tag + GitHub Release so tag-followers stop installing 0.6.1. |

> Consumer pins below were last live-verified **2026-08-22**. This environment
> still gets HTTP 404 on `gesh75/Gesh-Project` and `gesh75/gesh-project-trading` —
> those values are **not** re-confirmed this run. Do not invent newer pins.

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

Other env knobs do **not** use this parser. See the catalog in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#environment-variables).

DCF is measurement-only (rule #47). v0.8.2 added in-repo characterization tests
(`tests/test_dcf.py`), disclosed `capex_pct` / `nwc_pct` on every successful
result, and fail-closed named errors for empty-ratio / non-positive revenue
(PR #35). See [`docs/DCF.md`](docs/DCF.md).

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

## 3. Consumers and their pins — last GitHub-verified 2026-08-22

| Consumer | Pin (2026-08-22) | Form | Status then |
|---|---|---|---|
| `gesh75/Gesh-Project` | `493123938a173d890c63655ea20410501bd8b9f0` (`v0.8.1`) | 40-char commit ✅ | 🟡 behind then-`main` — missing PR #34 |
| `gesh75/gesh-project-trading` | `33af7482c01b4950cab82ba5167e47146f048575` (`v0.8.0`) | 40-char commit ✅ | 🟡 behind then-`main` — missing v0.8.1 + PR #34 |

This run **could not re-read** those `requirements.txt` files (GitHub API 404).
If the 2026-08-22 pins are still in place they are now also missing 0.8.2
(PR #35) and the CI fd-limit fix (PR #46). Re-verify before bumping.

After pins are confirmed, bump **both** to `56f14d4e`. Trading in particular
must not stay on a wheel that drops `NOTICE.md` / `LICENSE-cookbooks`.

## 4. Milestones

| State | Item | Exit gate |
|---|---|---|
| ✅ DONE | P0-B strict safety booleans (PR #8) | merged; CI green on 3.12/3.13/3.14 |
| ✅ DONE | `EffectiveConfig` identity + 0.6.2 (PR #11) | merged as `a9342c08` |
| ✅ DONE | Decision ledger Phase 4A | schema + hash contracts + tenant isolation |
| ✅ DONE | `gesh_core.dcf` v0.7.0 / methodology v0.8.0 / wheel LICENSE v0.8.1 | PRs #31–#33 |
| ✅ DONE | Fail-closed hardening batch (PRs #12–#30, #34) | allocation, kelly, ledger, tax, ECG, ATR, CI token |
| ✅ DONE | 0.8.2 DCF tests + fail-closed ratio/revenue + CI import discovery | PR #35 (`86d9e08`) |
| ✅ DONE | CI fd-limit raise for Buildkite GHA EMFILE | PR #46 (`56f14d4e`) |
| ⬜ NEXT | Consumer pin bump (product + engine) to `56f14d4e` | dedicated PRs in those repos; re-verify pins first |
| ⬜ NEXT | Annotated tag `v0.8.2` + GitHub Release | so tag-followers stop at 0.6.1 |
| ⬜ BACKLOG | Root LICENSE file (legal decision — not invented here) | owner call |
| ⬜ BACKLOG | Split files over the 400-line copilot guideline (`ledger/integration` 618, `state` 550, `kelly` 544) | non-breaking extract |

## 5. Achievements (since last control refresh)

- **PR #46 — CI fd limit.** pytest step raises `ulimit -n` so Buildkite 3.13/3.14
  no longer die with `EMFILE` under coverage + sqlite fixtures.
- **PR #35 — 0.8.2.** DCF characterization tests; empty-ratio / zero-revenue
  fail closed; `capex_pct` / `nwc_pct` disclosed; CI import discovery.
- **PR #34 — unhashable trade actions.** Allocation gate rejects non-hashable
  actions fail-closed.
- **PR #33 — vendor LICENSE in the wheel.** MIT attribution travels with the
  installed package.
- **PR #32 — DCF methodology.** Operating NWC, Blume beta + fragility,
  average-ratio base, named refusals.
- **PR #31 — `gesh_core.dcf`.** Shared deterministic valuation, measurement-only.
- **PRs #12–#30 — fail-closed pass.** Wash-sale `/tmp` fallback removed,
  snapshot hash validation, nested-secret strip, Kelly haircuts, source
  spoofing, ATR amplification bound, ECG NaN, CI token lockdown.

## 6. Blockers and risks

| Sev | Item | Evidence | Unblock condition |
|---|---|---|---|
| HIGH | No Git tag / Release past `v0.6.1` | `gh api repos/gesh75/gesh-core/tags`; Releases list empty | cut `v0.8.2` after pin bump; never move tags |
| HIGH | Engine / product pins not re-verified this run | consumer repos 404 from this environment | re-read `requirements.txt` when access exists; bump to `56f14d4e` |
| MEDIUM | Many open draft PRs | 34 open / 32 drafts on 2026-09-07, including docs #37 and #57 | owner triage; do not merge from this docs pass |
| LOW | No root LICENSE | tree has only `dcf/vendor/LICENSE-cookbooks` | owner decides SPDX; do not invent |
| LOW | Copilot 400-line guideline exceeded | `ledger/integration.py` 618, `state.py` 550, `kelly.py` 544 | extract, don't rewrite |

## 7. Execution queue

1. Re-verify consumer pins when those repos are readable.
2. Bump `gesh-project-trading` and `Gesh-Project` to `56f14d4e`.
3. Cut annotated tag `v0.8.2` and a GitHub Release. Pin-by-SHA remains the rule.
4. Decide a root LICENSE. Until then the package has no SPDX identifier.

**One writer per repository at a time.**

## 8. Verification evidence

| Claim | Evidence |
|---|---|
| `main` = `56f14d4e` | GitHub commits API, 2026-09-07 (unchanged since 2026-08-27) |
| CI green on that head | Actions run `33033241239`, `head_sha=56f14d4e`, conclusion `success` |
| Product / engine pins | **not re-verified this run** (404). Last live read 2026-08-22: product `49312393`, engine `33af7482` |
| Latest tag is `v0.6.1` | `list_tags`; peeled SHA `f11c460f…`; no `v0.7` / `v0.8` |
| No GitHub Releases | `list_releases` empty |
| DCF tested on `main` | `tests/test_dcf.py` (22 `test_*`) at `56f14d4e` |
| In-repo tests | 329 `test_*` across 25 files |

## 9. Definition of done

A change is done when: merged to `main`; CI green on the **exact** head SHA;
verified in a disposable checkout where a database or runtime is involved;
consumers' pins and control documents updated; and the runtime/deploy decision
recorded explicitly — including when the decision is "no deployment".

## Change log

| Date | Change | Not changed |
|---|---|---|
| 2026-09-07 | Re-verified `main` still `56f14d4e`; open-PR count 34/32 drafts; docs inventory + env-var catalog | no consumer pin changed *by this repo*; no runtime; no LICENSE invented; no draft PRs merged |
| 2026-08-31 | Control header + milestones rewritten against live `56f14d4e`; DCF tests and CI fd-limit recorded; consumer pins marked unverified (404) | same constraints |
| 2026-08-22 | 0.8.2: DCF tests + fail-closed empty-ratio/zero-revenue + disclosed capex/nwc; CI import discovery | no consumer pin changed *by this repo* |
| 2026-08-11 | PR #34 merged (`97a519b7`): reject unhashable trade actions | docs later refreshed in 0.8.2 |
| 2026-08-08 | PRs #31–#33: DCF module, methodology, vendor LICENSE in wheel (0.7.0 → 0.8.1) | no tag/release cut |
| 2026-07-31 | PR #11 merged (`a9342c08`): `EffectiveConfig` hashable, version `0.6.2` | no consumer pin changed by this repo |
