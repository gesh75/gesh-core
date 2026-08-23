# gesh-core

[![CI](https://github.com/gesh75/gesh-core/actions/workflows/ci.yml/badge.svg)](https://github.com/gesh75/gesh-core/actions/workflows/ci.yml)

Shared core package for the GESH Financial two-repo system. It is the single
source of truth for modules that were previously duplicated (and drifting)
across:

- **engine** — `~/Projects/gesh-project-trading` (port 9003)
- **product** — `~/Projects/gesh-project` (port 9000)

Declared version: **0.8.1** (`pyproject.toml` and `gesh_core.__version__`).
**Pin consumers by 40-char commit SHA, never by tag** — the latest release tag
is still `v0.6.1` and does not include DCF, ledger, or later contract fixes.

## 🎛 Project control

- **[PROJECT_CONTROL.md](PROJECT_CONTROL.md)** — control document: verified
  `main` SHA, the strict safety-boolean contract, consuming repositories and
  their last-recorded pins, compatibility gates, and blockers.

## 📊 Docs & diagrams

- **[docs/architecture.html](docs/architecture.html)** — interactive architecture dashboard (module map, shim pattern, DB resolution).
- **[docs/consensus-comparison.html](docs/consensus-comparison.html)** — engine vs product consensus + convergence roadmap.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/DCF.md](docs/DCF.md) · [docs/LEDGER_PHASE4A.md](docs/LEDGER_PHASE4A.md) · [docs/CONSENSUS_CONVERGENCE.md](docs/CONSENSUS_CONVERGENCE.md) · [PHASE3_STATUS.md](PHASE3_STATUS.md)

## Why

A 2026-06-19 audit found 46 duplicated modules, so every fix had to be
hand-synced across both repos. `gesh-core` removes that drift: each repo
depends on this package and keeps only a thin re-export shim where the module
used to live, so existing import paths (`import allocation_config`,
`from trading import levels`) keep working unchanged.

## Layout

src-layout (`src/gesh_core/...`) — forces a real install so missing files
surface immediately instead of silently resolving from the repo root.

## Local install (each consumer repo)

Clone side-by-side under `~/Projects/`, then from each repo's venv:

```bash
pip install -e ../gesh-core
```

Launch the consumer from its repo root (or set `GESH_DB_PATH` /
`GESH_CONFIG_PATH`). Database probe failure is fatal — there is no `/tmp`
fallback.

## Extraction status

- **Phase 3 (complete):** `allocation_config`, `ecg`, `kelly`, `tax_harvester`,
  `db`, `trading.{contract,config,state,risk_gate_core,levels,indicators}`.
- **Later (in tree):** `db_path`, `market_fetch`, `sentiment_connector`,
  `trading.autopilot_core`, `gesh_core.ledger`, `gesh_core.dcf` (0.7.0–0.8.1).
- **Still per-repo by design:** `trading.tracker` / `metrics` / `tracker_weekly`,
  each repo's `risk_gate.evaluate()`, and `consensus` (two different engines).

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for interfaces and pitfalls.

## Tests

`tests/` holds characterization/parity tests that pin behavior so an
extraction cannot silently regress. Run with `pytest`. This tree currently
has 303 `test_*` functions; DCF has no in-repo tests yet — see
[docs/DCF.md](docs/DCF.md).
