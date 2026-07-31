# gesh-core — Project Control

> Canonical control document for this repository. Linked from [README.md](README.md).
> **Verified 2026-07-31 against live GitHub.** Local-only claims are labelled as such.

## Control header

| Field | Value |
|---|---|
| Repository | `gesh75/gesh-core` |
| Remote | `https://github.com/gesh75/gesh-core.git` (private) |
| Verified `main` | `a9342c08d2867ecaf24733fa3f626a79761e381e` |
| Verification timestamp | 2026-07-31, `git fetch` + `gh` against the live remote |
| Declared version on `main` | `0.6.2` (`pyproject.toml` and `__init__.py` agree) |
| Latest release tag | `v0.6.1` → peeled commit `f11c460f628fea484c739b6ab25ea0e12c0c8f85` (now 4 commits behind `main`) |
| Open PRs | this one (docs) |
| Runtime | none — this is a library; it has no service, scheduler or database of its own |
| Last completed milestone | **`EffectiveConfig` identity fixes + 0.6.2 release** (PR #11, merged as `a9342c08`) |
| Single next action | **Bump the `gesh-project-trading` pin off the symbolic tag `v0.4.0`** (PR #41). |

> ✅ **Version-string caveat RESOLVED (2026-07-31).** `main` previously declared
> `__version__ = "0.6.1"` — identical to the `v0.6.1` tag it was 2 commits past —
> so a version comparison could not distinguish the two trees. PR #11 bumped it to
> **`0.6.2`**. Pinning by 40-char commit SHA remains the rule for consumers, but
> the version string is now honest.

## 1. Current truth

The strict safety-boolean contract is merged and is the reason this revision exists.

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

- **Invalid input is never silently coerced to `False`.** The pre-P0-B parser
  mapped every unrecognised token to `False`, silently disabling a safety gate.
- Both public paths fail closed — `load_risk_config()` **and**
  `effective_config()` raise; neither returns a usable fallback.
- Raw environment values never appear in metadata or exception messages
  (`<missing>` / `<redacted>` only).
- `effective_config()` returns an immutable settings mapping and a deterministic
  `config_hash` over *name · source · parsed value · validation status* for the
  three variables, with `resolved_at` excluded from the hash.

## 2. Architecture

Pure library. No service, port, scheduler or datastore.

```
src/gesh_core/
  trading/config.py         strict safety-boolean contract  ← P0-B
  trading/risk_gate_core.py contract.py  indicators.py  levels.py  state.py
  kelly.py  ecg.py  db.py  market_fetch.py  tax_harvester.py
  allocation_config.py  ledger/
```

Trust boundary: consumers import `gesh_core.*` directly, and both product repos
alias their local `trading/config.py` onto it via `sys.modules[__name__] = _impl`,
so **every module-level name here is reachable as `trading.config.X` downstream**.

## 3. Consumers and their pins — GitHub-verified 2026-07-31

| Consumer | Pin | Form | Status |
|---|---|---|---|
| `gesh75/Gesh-Project` | `d4e9f467c8fcb1ec952245469f6ac15d16a52075` on `main` | 40-char commit ✅ | 🟢 **integrated** — [PR #116](https://github.com/gesh75/Gesh-Project/pull/116) merged 2026-07-30 |
| `gesh75/gesh-project-trading` | **`v0.4.0`** (commit `f968be73`) | **symbolic tag ❌** | 🔴 23 commits behind; **does not have the strict validator**. Fix open: [PR #41](https://github.com/gesh75/gesh-project-trading/pull/41) |

`Gesh-Project` enforces commit-form pinning with
`tests/test_dependency_sanity.py::test_no_symbolic_gesh_core_ref_in_any_install_path`
and additionally asserts the **installed** distribution matches the pin.
`gesh-project-trading` has **no equivalent guard** — see Blockers.

## 4. Milestones

| State | Item | Exit gate |
|---|---|---|
| ✅ DONE | P0-B strict safety booleans (PR #8, `d4e9f467`) | merged; CI green on the exact head across Python 3.12/3.13/3.14 |
| ✅ DONE | `Gesh-Project` integration evidence | [PR #116](https://github.com/gesh75/Gesh-Project/pull/116) merged 2026-07-30 as `74ba35b2`; 120 focused + 2,297 full-suite tests green against the reconciled base |
| ✅ DONE | `EffectiveConfig` identity + `0.6.2` bump | [PR #11](https://github.com/gesh75/gesh-core/pull/11) merged as `a9342c08`; hashable, `resolved_at` excluded from `__eq__`, cross-wire gap closed |
| 🟡 ACTIVE | `gesh-project-trading` pin modernisation | [PR #41](https://github.com/gesh75/gesh-project-trading/pull/41): symbolic tag → commit SHA + a no-symbolic guard test |

## 5. Achievements

- **PR #11 — `EffectiveConfig` identity + 0.6.2.** Merged as `a9342c08`. Fixed a
  frozen-but-unhashable dataclass (`hash()` raised `TypeError` while
  `hash(RiskConfig())` worked) and an `__eq__` that included `resolved_at`, so two
  reads of an *unchanged* configuration never compared equal. Closed the test gap
  where `require_approval` and `market_regime_gate` were mutually indistinguishable.
  All four regression mutations caught; 327 tests pass.
- **PR #116 (consumer) — P0-B integrated.** `Gesh-Project` merged the `d4e9f467`
  pin 2026-07-30 as `74ba35b2`, with 120 focused + 2,297 full-suite tests green and
  source-database hashes proven byte-identical.
- **PR #8 — strict safety booleans.** Merged as `d4e9f467`. Reviewed at exact
  head `53690821`; CI run `30385897321` green on all four jobs (lint + tests on
  3.12/3.13/3.14). Test coverage grew from 86 to 87 items in the strict-config
  file, with an exact-SHA canonical hash oracle, frozen-dataclass regression
  coverage on both the outer and nested dataclasses, and full metadata assertions
  including `ConfigSetting.name`.

## 6. Blockers and risks

| Sev | Item | Evidence | Unblock condition |
|---|---|---|---|
| HIGH | `gesh-project-trading` pins gesh-core by symbolic tag `v0.4.0` | `requirements.txt:38`; `v0.4.0` = commit `f968be73`, whose parser is the lenient `raw.strip().lower() in {"1","true","yes","y","on"}` | dedicated dependency PR in that repo bumping to a 40-char commit, with a full test run and a symbolic-ref guard test |
| HIGH | `gesh-project-trading` CI could not install this package | its `GESH_CORE_PAT` was the stale 2026-06-29 token while `Gesh-Project`'s was rotated 2026-07-29; the failure stayed invisible because every trading change since was Markdown-only and path-filtered out of CI | **resolved 2026-07-31** — token rotated; PR #41 re-run |
| MEDIUM | the live trading service imports this package as an **editable install** | its venv records `{"dir_info": {"editable": true}, "url": "file:///Users/georgigaydarov/Projects/gesh-core"}`, so a `git checkout` in a developer worktree changes live service behaviour | reinstall that venv from a pinned VCS ref (runtime change — separate gate) |
| ~~LOW~~ | ~~`EffectiveConfig` frozen but unhashable; `__eq__` includes `resolved_at`~~ | **RESOLVED 2026-07-31** by PR #11 (`a9342c08`): `settings` is `field(hash=False)`, `resolved_at` is `field(compare=False)` | — |

## 7. Execution queue

1. ~~`Gesh-Project` PR #116~~ — **done** (merged 2026-07-30, `74ba35b2`).
2. ~~`0.6.2` version bump~~ — **done** (merged 2026-07-31, `a9342c08`).
3. `gesh-project-trading` dependency modernisation — [PR #41](https://github.com/gesh75/gesh-project-trading/pull/41), open.

**One writer per repository at a time.** The contract is now proven in a consumer,
so core work may resume — but the trading pin should land first so both consumers
run the same validated revision.

## 8. Verification evidence

| Claim | Evidence |
|---|---|
| `main` = `a9342c08` | `git rev-parse origin/main` after `git fetch --all --prune`, 2026-07-31 |
| PR #11 CI green on its exact head | run `30529711894`, `head_sha=3f56651f…`, 4/4 jobs `success` |
| PR #8 CI green on exact head | GitHub Actions run `30385897321`, `head_sha=53690821…`, 4/4 jobs `success` |
| Strict contract behaves as documented | contract extracted from the merged source and executed over the full accept/reject matrix; 13 invalid input classes raise, numeric `0` accepted |
| Consumer pins | `gh api repos/<consumer>/contents/requirements.txt`, decoded, 2026-07-30 |

## 9. Local-worktree inventory (local-only claim, 2026-07-30)

| Path | Branch / HEAD | State |
|---|---|---|
| `/Users/georgigaydarov/Projects/gesh-core` | `fix/p0-strict-safety-config` @ `53690821` | clean; 1 ahead / 2 behind `origin/main` (the PR branch, now merged upstream) |
| `/private/tmp/gesh-core-p0b-baseline-uZd2Ve` | detached @ `061af708` | throwaway review baseline |
| `/private/tmp/gesh-p0b-disp-LCpUrr/worktree` | detached @ `3d3e8b29` | **prunable** — gitdir points to a non-existent location |

## 10. Definition of done

A change is done when: merged to `main`; CI green on the **exact** head SHA;
verified in a disposable checkout where a database or runtime is involved;
consumers' pins and control documents updated; and the runtime/deploy decision
recorded explicitly — including when the decision is "no deployment".

## Change log

| Date | Change | Not changed |
|---|---|---|
| 2026-07-31 | PR #11 merged (`a9342c08`): `EffectiveConfig` hashable, `resolved_at` out of `__eq__`, cross-wire test gap closed, version `0.6.2`. This document refreshed to match. | no consumer pin changed by this repo; no runtime touched |
| 2026-07-30 | `PROJECT_CONTROL.md` created; consumer pin divergence recorded | no source, test, dependency or CI change |
| 2026-07-28 | PR #8 merged as `d4e9f467` — strict safety-boolean validation | no runtime, no consumer pin |
