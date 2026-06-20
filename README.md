# gesh-core

Shared core package for the GESH Financial two-repo system. It is the single
source of truth for modules that were previously duplicated (and drifting)
across:

- **engine** — `~/Projects/gesh-project-trading` (port 9003)
- **product** — `~/Projects/gesh-project` (port 9000)

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
