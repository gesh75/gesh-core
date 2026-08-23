# gesh-core — Project Control

> Canonical control document for this repository. Linked from [README.md](README.md).
> **Verified 2026-08-22 against live GitHub.** Local-only claims are labelled as such.

## Control header

| Field | Value |
|---|---|
| Repository | `gesh75/gesh-core` |
| Remote | `https://github.com/gesh75/gesh-core.git` (private) |
| Verified `main` (pre-0.8.2) | `97a519b75406abdc7b2be36d5633dd18c0f2c0b5` |
| Verification timestamp | 2026-08-22, GitHub API against the live remote |
| Declared version on `main` | `0.8.2` (`pyproject.toml` and `__init__.py` agree after this revision) |
| Latest release tag | `v0.6.1` → peeled commit `f11c460f…` (**no tags for 0.7.0 / 0.8.0 / 0.8.1 / 0.8.2**) |
| GitHub Releases | **none** |
| Open PRs / issues | none at verification |
| Runtime | none — this is a library; it has no service, scheduler or database of its own |
| Last completed milestone | **PR #34** `fix(allocation): reject unhashable trade actions` (merged as `97a519b7`) |
| Single next action | **Bump both consumer pins to this 0.8.2 SHA** (see §3). Then cut an annotated `v0.8.2` tag + GitHub Release so tag-followers stop installing 0.6.1. |

> ⚠ **This document was stale from 2026-07-31 through 2026-08-22.** It still
> claimed version `0.6.2`, SHA `a9342c08`, and "trading still pins symbolic tag
> `v0.4.0`". Live truth at verification: version `0.8.1` on `97a519b7`, both
> consumers already pin 40-char SHAs, trading's tag pin is gone.

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

## 3. Consumers and their pins — GitHub-verified 2026-08-22

| Consumer | Pin | Form | Status |
|---|---|---|---|
| `gesh75/Gesh-Project` | `493123938a173d890c63655ea20410501bd8b9f0` (`v0.8.1`) | 40-char commit ✅ | 🟡 **1 commit behind `main`** — missing PR #34 (unhashable allocation actions). `requirements.txt` |
| `gesh75/gesh-project-trading` | `33af7482c01b4950cab82ba5167e47146f048575` (`v0.8.0`) | 40-char commit ✅ | 🟡 **2 commits behind `main`** — missing v0.8.1 (vendor LICENSE in the wheel) **and** PR #34 |

The 2026-07-31 claim that trading still pinned symbolic tag `v0.4.0` is **obsolete**.
Both consumers pin SHAs. The remaining risk is **lag**, not tag-following.

After this 0.8.2 lands, bump **both** pins to the merge SHA of this revision.
Trading in particular still installs a wheel that drops `NOTICE.md` /
`LICENSE-cookbooks` (the product repo's
`test_vendored_code_keeps_its_licence_and_notice` would fail against that pin).

## 4. Milestones

| State | Item | Exit gate |
|---|---|---|
| ✅ DONE | P0-B strict safety booleans (PR #8) | merged; CI green on 3.12/3.13/3.14 |
| ✅ DONE | `EffectiveConfig` identity + 0.6.2 (PR #11) | merged as `a9342c08` |
| ✅ DONE | Decision ledger Phase 4A | schema + hash contracts + tenant isolation |
| ✅ DONE | `gesh_core.dcf` v0.7.0 / methodology v0.8.0 / wheel LICENSE v0.8.1 | PRs #31–#33 |
| ✅ DONE | Fail-closed hardening batch (PRs #12–#30, #34) | allocation, kelly, ledger, tax, ECG, ATR, CI token |
| 🟡 ACTIVE | 0.8.2 DCF tests + control-doc refresh + CI import discovery | this revision |
| ⬜ NEXT | Consumer pin bump (product + engine) to 0.8.2 SHA | dedicated PRs in those repos |
| ⬜ NEXT | Annotated tag `v0.8.2` + GitHub Release | so tag-followers stop at 0.6.1 |
| ⬜ BACKLOG | Root LICENSE file (legal decision — not invented here) | owner call |
| ⬜ BACKLOG | Split files over the 400-line copilot guideline (`ledger/integration` 618, `state` 550, `kelly` 544) | non-breaking extract |

## 5. Achievements (since last control refresh)

- **PR #34 — unhashable trade actions.** Allocation gate rejects non-hashable actions fail-closed.
- **PR #33 — vendor LICENSE in the wheel.** MIT attribution travels with the installed package.
- **PR #32 — DCF methodology.** Operating NWC, Blume beta + fragility, average-ratio base, named refusals.
- **PR #31 — `gesh_core.dcf`.** Shared deterministic valuation, measurement-only.
- **PRs #12–#30 — fail-closed pass.** Wash-sale `/tmp` fallback removed, snapshot hash validation, nested-secret strip, Kelly haircuts, source spoofing, ATR amplification bound, ECG NaN, CI token lockdown.

## 6. Blockers and risks

| Sev | Item | Evidence | Unblock condition |
|---|---|---|---|
| HIGH | No Git tag / Release past `v0.6.1` | `gh api repos/gesh75/gesh-core/tags`; Releases list empty | cut `v0.8.2` after this lands; never move tags |
| HIGH | Engine pin is two commits behind | `gesh-project-trading/requirements.txt` → `33af7482` (v0.8.0) | bump to 0.8.2 SHA; run engine suite |
| MEDIUM | Product pin is one commit behind | `Gesh-Project/requirements.txt` → `49312393` (v0.8.1) | bump to 0.8.2 SHA |
| MEDIUM | DCF had zero in-repo tests until 0.8.2 | no `tests/test_dcf.py` on `97a519b7` | this revision |
| MEDIUM | Control docs lagged 3+ weeks | `PROJECT_CONTROL.md` still said 0.6.2 / trading `v0.4.0` | this revision |
| LOW | No root LICENSE | tree has only `dcf/vendor/LICENSE-cookbooks` | owner decides SPDX; do not invent |
| LOW | CI import list was a stale allow-list | omitted dcf/ledger/sentiment/market_fetch/autopilot | filesystem discovery in this revision |
| LOW | Copilot 400-line guideline exceeded | `ledger/integration.py` 618, `state.py` 550, `kelly.py` 544 | extract, don't rewrite |

## 7. Execution queue

1. Land 0.8.2 (this revision) — DCF tests, fail-closed ratio/revenue, disclosed capex/nwc, CI discovery, control docs.
2. Bump `gesh-project-trading` pin `33af7482` → 0.8.2 SHA (wheel LICENSE + unhashable actions + DCF tests).
3. Bump `Gesh-Project` pin `49312393` → 0.8.2 SHA.
4. Cut annotated tag `v0.8.2` and a GitHub Release. Pin-by-SHA remains the rule.
5. Decide a root LICENSE. Until then the package has no SPDX identifier.

**One writer per repository at a time.**

## 8. Verification evidence

| Claim | Evidence |
|---|---|
| `main` = `97a519b7` before this revision | GitHub contents SHA, 2026-08-22 |
| CI green on that head | Actions run `31493540985`, `head_sha=97a519b7`, conclusion `success` |
| Product pin | `Gesh-Project/requirements.txt` line `gesh-core @ git+…@49312393…` |
| Engine pin | `gesh-project-trading/requirements.txt` line `gesh-core @ git+…@33af7482…` |
| Latest tag is `v0.6.1` | `list_tags`; no `v0.7` / `v0.8` |
| No GitHub Releases | `list_releases` empty |
| DCF untested on `main` | tree has no `tests/test_dcf*.py` at `97a519b7` |

## 9. Definition of done

A change is done when: merged to `main`; CI green on the **exact** head SHA;
verified in a disposable checkout where a database or runtime is involved;
consumers' pins and control documents updated; and the runtime/deploy decision
recorded explicitly — including when the decision is "no deployment".

## Change log

| Date | Change | Not changed |
|---|---|---|
| 2026-08-22 | 0.8.2: DCF tests + fail-closed empty-ratio/zero-revenue + disclosed capex/nwc; CI import discovery; this document rewritten against live GitHub | no consumer pin changed *by this repo*; no runtime; no LICENSE invented |
| 2026-08-11 | PR #34 merged (`97a519b7`): reject unhashable trade actions | docs not refreshed (this gap) |
| 2026-08-08 | PRs #31–#33: DCF module, methodology, vendor LICENSE in wheel (0.7.0 → 0.8.1) | no tag/release cut |
| 2026-07-31 | PR #11 merged (`a9342c08`): `EffectiveConfig` hashable, version `0.6.2` | no consumer pin changed by this repo |
