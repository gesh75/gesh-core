# gesh-core

[![CI](https://github.com/gesh75/gesh-core/actions/workflows/ci.yml/badge.svg)](https://github.com/gesh75/gesh-core/actions/workflows/ci.yml)

Shared core package for the GESH Financial two-repo system. It is the single
source of truth for modules that were previously duplicated (and drifting)
across:

- **engine** — `~/Projects/gesh-project-trading` (port 9003)
- **product** — `~/Projects/gesh-project` (port 9000)

## 🎛 Project control

- **[PROJECT_CONTROL.md](PROJECT_CONTROL.md)** — canonical control document:
  verified `main` SHA, the strict safety-boolean contract, consuming repositories
  and their pins, compatibility gates, blockers, and the single next action.
  **Pin by 40-char commit SHA, never by tag** — `main` still declares
  `__version__ "0.6.1"`, identical to the `v0.6.1` tag it is 2 commits past.

## 📊 Docs & diagrams

- **[docs/architecture.html](docs/architecture.html)** — interactive architecture dashboard (module map, shim pattern, DB resolution).
- **[docs/consensus-comparison.html](docs/consensus-comparison.html)** — engine vs product consensus + convergence roadmap.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/CONSENSUS_CONVERGENCE.md](docs/CONSENSUS_CONVERGENCE.md) · [PHASE3_STATUS.md](PHASE3_STATUS.md)

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

## Extraction status (Phase 3)

- **Tier 1 (this session):** `allocation_config`, `trading.levels`,
  `trading.contract`, `trading.metrics`.
- **Tier 2 (later):** `ecg`, `kelly`, `tax_harvester`.
- **Tier 3 (later):** `trading.state` / `trading.config` / `trading.tracker`,
  `consensus` (needs design decisions).

## Tests

`tests/` holds the characterization/parity tests that pin behavior so an
extraction cannot silently regress. Run with `pytest`.
