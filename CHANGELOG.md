# Changelog

All notable changes to this package are recorded here. Version strings are
literals in `pyproject.toml`, `src/gesh_core/__init__.py`, and
`tests/test_package_version.py` — bumping requires editing all three.

## Unreleased

### Fixed
- Kelly leftover env knobs (`KELLY_CORR_THRESHOLD`, `KELLY_COST_BPS`,
  `KELLY_REBALANCE_DAYS`) reject NaN/infinity/malformed values with
  `ConfigError`. A NaN correlation threshold made `|corr| >= threshold`
  False for every pair, so the diversification haircut never applied.
  Non-finite cost drag poisoned half-Kelly to NaN so AVOID never fired.
  Empty env still means "use the conservative default".
- `kelly_size_holding` applies the AI valuation penalty AFTER the half-Kelly
  clamp to `MAX_POSITION_PCT`. Continuous Kelly is unbounded, so on a steady
  positive drift the pre-clamp multiplier was a no-op: an `AVOID` or `SELL`
  verdict still returned `action="ADD"` at the 25% ceiling. New hard
  invariant: `AVOID` sizes to `0.0`; `SELL` never targets more than the
  current weight, so neither verdict can ever recommend buying. `raw_kelly`
  now reports the blend before the penalty (the penalty is still exposed as
  `ai_penalty`); `optimal_pct` / `half_kelly` / `recommended_usd` carry it.
- `resolve_db_path` is path-only: no mkdir, connect, or CREATE/DROP at import
  or collection. Writability is an explicit `ensure_db_writable` bootstrap
  called from first `connect` / `_conn`. Importing `gesh_core.db` or
  `trading.state` against a read-only operational sentinel does not mutate it.
- `_max_drawdown` includes starting equity as the first peak. A −10% first
  return then flat is −10%, not 0.
- Numeric safety settings (`RiskConfig` env, Kelly unit-interval caps, and
  allocation file caps) reject NaN, infinity, negative caps, and malformed
  values with `ConfigError` instead of silently disabling gates. Empty env
  still means "use the conservative default" (launchd). Zero is valid only
  where documented (`MIN_ENTRY_SCORE`, `MAX_POSITION_PCT`, `MIN_CASH_BUFFER_USD`).
  `effective_config().config_hash` includes numeric limits and provenance.
- `paper_realized_pnl_usd_today` raises `LedgerUnavailable` when neither
  `paper_outcomes` nor `paper_trades` exists, instead of returning `0.0`.
  One missing table is still skipped (two-book design). An empty present
  table is a measured flat day.
- `validate_action` runs size, position, cash, and price checks even when
  `auto_trade` is OFF. Paper callers can pass `require_live_permission=False`
  to skip only live execution permission. Returns `ActionCheck` (still
  unpackable as `ok, reason = ...`) with a structured `code`.
- `validate_action` rejects non-finite / non-numeric trade size on every
  action, and non-finite cash on BUY/ADD (`NaN > cap` is False in IEEE-754).
  SELL/TRIM ignore a dirty cash snapshot so emergency exits are not blocked.
- `entry_floor_blocks` treats non-finite `raw_score` / `min_entry_score` as
  blocked on BUY. SELL/HOLD stay ungated.
- `TradeIntent.validate` rejects non-finite stop / take-profit.

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
