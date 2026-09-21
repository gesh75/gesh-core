# gesh-core

[![CI](https://github.com/gesh75/gesh-core/actions/workflows/ci.yml/badge.svg)](https://github.com/gesh75/gesh-core/actions/workflows/ci.yml)

Shared core package for the GESH Financial two-repo system. It is the single
source of truth for modules that were previously duplicated (and drifting)
across:

- **engine** — `gesh-project-trading` (port 9003)
- **product** — `Gesh-Project` (port 9000)

Current declared version: **0.8.2**. Pin consumers by **40-char commit SHA**,
never by tag — the latest Git tag is still `v0.6.1`.

## Project control

- **[PROJECT_CONTROL.md](PROJECT_CONTROL.md)** — canonical control document:
  verified `main` SHA, the strict safety-boolean contract, consuming repositories
  and their pins, compatibility gates, blockers, and the single next action.

## Docs & diagrams

- **[docs/architecture.html](docs/architecture.html)** — interactive architecture dashboard (module map, shim pattern, DB resolution).
- **[docs/consensus-comparison.html](docs/consensus-comparison.html)** — engine vs product consensus + convergence roadmap.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/DCF.md](docs/DCF.md) · [docs/CONSENSUS_CONVERGENCE.md](docs/CONSENSUS_CONVERGENCE.md) · [docs/LEDGER_PHASE4A.md](docs/LEDGER_PHASE4A.md) · [PHASE3_STATUS.md](PHASE3_STATUS.md) · [CHANGELOG.md](CHANGELOG.md)

## Why

A 2026-06-19 audit found 46 duplicated modules, so every fix had to be
hand-synced across both repos. `gesh-core` removes that drift: each repo
depends on this package and keeps only a thin re-export shim where the module
used to live, so existing import paths (`import allocation_config`,
`from trading import levels`) keep working unchanged.

## Layout

src-layout (`src/gesh_core/...`) — forces a real install so missing files
surface immediately instead of silently resolving from the repo root.

```
src/gesh_core/
  allocation_config.py   kelly.py   ecg.py   tax_harvester.py
  db.py   db_path.py   market_fetch.py   sentiment_connector.py
  trading/               config, contract, indicators, levels,
                         risk_gate_core, state, autopilot_core
  dcf/                   fair_value, inputs, sensitivity + vendored cookbook
  ledger/                canonical hashes, schema, repository, daily adapter
```

Phase 3 de-drift is complete. Phase 4A (decision ledger) and `gesh_core.dcf`
(deterministic valuation) landed afterwards. `main` after 0.8.2 also carries
the fail-closed numeric/permission batch and `precision_overlay_blocks` —
see `CHANGELOG.md` Unreleased and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Local install (each consumer repo)

Clone side-by-side under `~/Projects/`, then from each repo's venv:

```bash
pip install -e ../gesh-core
```

Production / CI must pin a 40-char commit:

```
gesh-core @ git+https://github.com/gesh75/gesh-core.git@<full-sha>
```

## Tests

`tests/` holds the characterization/parity tests that pin behavior so an
extraction cannot silently regress. Run with `pytest`. CI also runs ruff + mypy
and a filesystem-driven import of every non-vendored module.
