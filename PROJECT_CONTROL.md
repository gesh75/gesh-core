# gesh-core — Project Control

> Canonical control document for this repository. Linked from [README.md](README.md).
> **Verified 2026-07-30 against live GitHub.** Local-only claims are labelled as such.

## Control header

| Field | Value |
|---|---|
| Repository | `gesh75/gesh-core` |
| Remote | `https://github.com/gesh75/gesh-core.git` (private) |
| Verified `main` | `d4e9f467c8fcb1ec952245469f6ac15d16a52075` |
| Verification timestamp | 2026-07-30, `git fetch` + `gh` against the live remote |
| Latest release tag | `v0.6.1` → peeled commit `f11c460f628fea484c739b6ab25ea0e12c0c8f85` |
| Open PRs | none |
| Runtime | none — this is a library; it has no service, scheduler or database of its own |
| Last completed milestone | **P0-B strict safety-boolean configuration** (PR #8, merged as `d4e9f467`) |
| Single next action | **Consumer integration evidence, not more core refactoring.** |

> ⚠️ **Version-string caveat.** `main` (`d4e9f467`) still declares
> `__version__ = "0.6.1"` — identical to the `v0.6.1` tag, which is 2 commits
> behind it. A version comparison **cannot** distinguish the two trees; only the
> 40-char commit SHA can. Consumers must pin by commit. A `0.6.2` bump is
> outstanding.

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

## 3. Consumers and their pins — GitHub-verified 2026-07-30

| Consumer | Pin | Form | Status |
|---|---|---|---|
| `gesh75/Gesh-Project` | `f11c460f628fea484c739b6ab25ea0e12c0c8f85` on `main`; **`d4e9f467…` proposed** in draft [PR #116](https://github.com/gesh75/Gesh-Project/pull/116) | 40-char commit ✅ | 🟡 integration draft open, awaiting owner merge |
| `gesh75/gesh-project-trading` | **`v0.4.0`** (commit `f968be73`) | **symbolic tag ❌** | 🔴 several releases behind; **does not have the strict validator** |

`Gesh-Project` enforces commit-form pinning with
`tests/test_dependency_sanity.py::test_no_symbolic_gesh_core_ref_in_any_install_path`
and additionally asserts the **installed** distribution matches the pin.
`gesh-project-trading` has **no equivalent guard** — see Blockers.

## 4. Milestones

| State | Item | Exit gate |
|---|---|---|
| ✅ DONE | P0-B strict safety booleans (PR #8, `d4e9f467`) | merged; CI green on the exact head across Python 3.12/3.13/3.14 |
| 🟡 ACTIVE | `Gesh-Project` integration evidence | draft PR #116 merged after owner authorization |
| ⬜ NEXT | `0.6.2` version bump | `__version__` distinguishes this tree from the `v0.6.1` tag |
| 🔴 BLOCKED | `gesh-project-trading` pin modernisation | dedicated PR: symbolic tag → commit SHA, plus its own full test run |

## 5. Achievements

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
| MEDIUM | `__version__` stale at `0.6.1` on `main` | `src/gesh_core/__init__.py` and `pyproject.toml` both read `0.6.1` at `d4e9f467`, 2 commits past the `v0.6.1` tag | `0.6.2` release commit |
| LOW | `EffectiveConfig` is frozen but unhashable, and `__eq__` includes `resolved_at` | `settings` is a `MappingProxyType` over a dict; two calls under identical environment never compare equal | mark `resolved_at` with `compare=False`, or document `config_hash` as the identity |

## 7. Execution queue

1. Owner authorizes and merges `Gesh-Project` PR #116 (consumer integration evidence).
2. `0.6.2` version bump in this repo.
3. `gesh-project-trading` dependency modernisation (separate PR, separate gate).

**One writer per repository at a time.** No further core refactoring until step 1
proves the contract in a consumer.

## 8. Verification evidence

| Claim | Evidence |
|---|---|
| `main` = `d4e9f467` | `git rev-parse origin/main` after `git fetch --all --prune`, 2026-07-30 |
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
| 2026-07-30 | `PROJECT_CONTROL.md` created; consumer pin divergence recorded | no source, test, dependency or CI change |
| 2026-07-28 | PR #8 merged as `d4e9f467` — strict safety-boolean validation | no runtime, no consumer pin |
