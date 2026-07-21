# Decision Ledger — Phase 4A

**Branch:** `phase4a-ledger-foundation-v2`

**Scope:** Version contracts, canonical hashing, additive SQLite schema, tenant-scoped repository helpers.

## Explicit non-goals

Phase 4A does **not**:

- Integrate with analysis, paper trading, risk gate, Kelly, consensus, or Monte Carlo
- Add APIs or dashboard UI
- Implement Track Record V2 execution / fills
- Migrate or rewrite legacy `paper_trades` / `analysis_runs` data
- Claim AI output determinism

## Schema

Three additive tables (`CREATE TABLE IF NOT EXISTS`):

### `portfolio_snapshots`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| tenant_id | TEXT NOT NULL | |
| snapshot_hash | TEXT NOT NULL | content-addressed |
| captured_at | TEXT NOT NULL | UTC ISO |
| base_currency | TEXT | default USD |
| total_equity, cash, buying_power | REAL | |
| holdings_json | TEXT NOT NULL | |
| risk_state_json | TEXT | nullable |
| schema_version | INTEGER NOT NULL | |
| created_at | TEXT NOT NULL | |

**Constraint:** `UNIQUE (tenant_id, snapshot_hash)`

### `market_quote_snapshots`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| tenant_id | TEXT NOT NULL | |
| snapshot_hash | TEXT NOT NULL | |
| symbol, asset_type | TEXT | |
| provider | TEXT | |
| as_of, available_time, retrieved_at | TEXT | |
| bid, ask, last, volume | REAL | |
| quality_state | TEXT NOT NULL | CHECK enum |
| quality_reason, payload_json | TEXT | |
| schema_version, created_at | | |

**Constraint:** `UNIQUE (tenant_id, snapshot_hash)`  
**CHECK:** `quality_state IN ('FRESH','STALE','DEGRADED','MISSING','CONFLICTING')`

### `recommendations`

| Column | Type | Notes |
|--------|------|-------|
| recommendation_id | TEXT PK | |
| analysis_run_id | INTEGER | nullable |
| tenant_id, symbol, asset_type | TEXT | |
| context_hash | TEXT NOT NULL | |
| portfolio_snapshot_id | INTEGER FK | |
| market_quote_snapshot_id | INTEGER FK | |
| decision_at, source, action | TEXT | |
| conviction, confidence, target_position_pct | REAL | |
| stop_price, target_price | REAL | |
| consensus_json, quant_summary_json, ai_output_json | TEXT | |
| ai_provider, ai_model, prompt_bundle_hash | TEXT | |
| intent_id | INTEGER | nullable — not every rec becomes a trade |
| schema_version | INTEGER | |
| supersedes_recommendation_id | TEXT FK | corrections |
| created_at | TEXT | |

## Hash contracts

### Portfolio snapshot hash (`ps_*`)

**Includes:** tenant_id, base_currency, holdings sorted by symbol (symbol, quantity, avg_cost), cash, buying_power, total_equity, optional risk_state, schema version.

**Excludes:** captured_at, UI labels, secrets.

### Market quote snapshot hash (`mqs_*`)

**Includes:** tenant_id, symbol, asset_type, provider, as_of, available_time, retrieved_at, bid/ask/last/volume, quality_state, schema version.

### Analysis context hash (`ctx_*`)

**Includes:** tenant_id, source, portfolio_snapshot_hash, ordered market quote hashes, AI provider/model, prompt_bundle_hash, config_hash, version_bundle, context schema version.

**Excludes:** recommendation/AI output text, token usage, latency, hostnames, request IDs.

`context_hash` identifies **input context only**. It does not imply identical LLM output.

## Tenant model

- Every row requires non-empty `tenant_id`.
- Customer rows: canonical auth `user_id` (UUID string).
- Owner / daily-chain: `OWNER_TENANT_ID = "owner"` (never NULL).
- All getters filter by `tenant_id`; cross-tenant lookups return `None`.

## Money precision

Follows existing repository convention: SQLite `REAL` for monetary columns. Canonical hashing preserves `Decimal` via a type tag when present in hash inputs. **Limitation:** binary float storage is not exact for all decimal values; reconciliation should use the same convention as legacy paper tables.

## Migration procedure

1. Deploy code containing `gesh_core.ledger` and the `init_db()` hook.
2. On startup, `init_db()` calls `init_ledger_tables()` which runs `CREATE TABLE/INDEX IF NOT EXISTS`.
3. Safe on empty and populated databases. No data migration of legacy rows.

## Rollback procedure

1. Stop calling ledger repository helpers (none are wired into production paths in Phase 4A).
2. Optionally leave empty tables in place (harmless).
3. Do **not** drop tables that may contain data without backup and explicit operator decision.
4. Revert the `init_db()` ledger hook if desired; existing rows remain until manually removed.

## Compatibility guarantees

- No changes to `analysis_runs`, `equity_snapshots`, `paper_trades`, `trade_log`, or trading state tables.
- No changes to paper trading, risk gate, consensus, Kelly, or Monte Carlo behavior.
- Snapshots are content-addressed (insert-or-get by tenant + hash).
- Recommendations are append-only; duplicate `recommendation_id` raises `IntegrityError`.
- Corrections use `supersedes_recommendation_id` (no UPDATE of business fields).
