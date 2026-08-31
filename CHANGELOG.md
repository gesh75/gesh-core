# Changelog

All notable changes to this package are recorded here. Version strings are
literals in `pyproject.toml`, `src/gesh_core/__init__.py`, and
`tests/test_package_version.py` — bumping requires editing all three.

## Unreleased

### Docs

- Added `docs/DCF.md` (public API, CLI, methodology, refusals, sensitivity).
- Architecture markdown + HTML dashboards brought current to 0.8.2 (17 shared
  surfaces, 329 tests, fail-closed `db_path`, two action vocabularies).
- CI runbook: Buildkite GHA `ulimit -n` raise (PR #46) so pytest+coverage does
  not hit `EMFILE` on 3.13/3.14.

## 0.8.2 — 2026-08-22

### Fixed
- `_avg_ratio` no longer raises `ZeroDivisionError` when every revenue period is
  zero; `compute_fair_value` returns a named error dict instead.
- `value_with_assumptions` refuses non-positive revenue before the vendored
  cookbook model divides by it.
- `_growth_path` no longer divides by zero on a 0- or 1-year horizon.
- Financial-sector exclusion is now case-insensitive (`"financial services"`).
- DCF CLI module paths pointed at the pre-extraction `trading.dcf_*` names;
  they now name `gesh_core.dcf.*`. `python -m gesh_core.dcf` works.
- CI's hard-coded import list omitted `dcf`, `ledger`, `sentiment_connector`,
  `market_fetch`, `autopilot_core`, `db_path`. Discovery is now filesystem-driven.

### Added
- Characterization tests for `gesh_core.dcf` (the v0.7.0/v0.8.0 valuation engine
  previously shipped with **zero** tests in this repo).
- Direct ATR tests for `trading.indicators`.
- `capex_pct`, `nwc_pct`, and the NWC series are now disclosed on every
  successful `compute_fair_value` result (methodology review: assumptions must
  travel with the number).
- Coverage report in CI (`pytest --cov=gesh_core`); informational, no floor yet.

### Docs
- `PROJECT_CONTROL.md`, `README.md`, and `docs/ARCHITECTURE.md` brought current
  to `main` (they still described 0.6.1/0.6.2 and an 11-module Phase-3 surface).

## 0.8.1 — 2026-08-08

Packaging: wheel now ships `dcf/vendor/NOTICE.md` + `LICENSE-cookbooks`.

## 0.8.0 — 2026-08-08

DCF methodology revision: operating NWC, Blume beta + fragility flag,
average-ratio base, sector/margin/non-positive-price guards.

## 0.7.0 — 2026-08-08

`gesh_core.dcf` extracted from the engine (deterministic DCF).

## 0.6.2 — 2026-07-31

`EffectiveConfig` identity: hashable, `resolved_at` excluded from `__eq__`.
