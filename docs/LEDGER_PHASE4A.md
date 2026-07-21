# Decision Ledger — Phase 4A

**Branch:** `phase4a-ledger-foundation-v2`

**Scope:** Version contracts, canonical hashing, additive SQLite schema, tenant-scoped repository helpers.

## Explicit non-goals

Phase 4A does **not**:

- Integrate with analysis, paper trading, risk gate, Kelly, consensus, or Monte Carlo
- Add APIs or dashboard UI
- Implement Track Record V2 execution / fills
- Migrate or rewrite legacy `paper_trades` / `analysis_runs` data
- Claim AI output determinism or production readiness of the full decision pipeline

## Schema

Three additive tables (`CREATE TABLE IF NOT EXISTS`):

- **portfolio_snapshots** — `UNIQUE (tenant_id, snapshot_hash)`
- **market_quote_snapshots** — `UNIQUE (tenant_id, snapshot_hash)`; quality_state CHECK enum
- **recommendations** — append-only; PK `recommendation_id`; optional FKs to snapshots and supersedes

## Foreign-key and connection policy

- `PRAGMA foreign_keys = ON` is set for **every** connection returned by `gesh_core.db.connect()`.
- `init_ledger_tables()` also enables `PRAGMA foreign_keys = ON` on any connection it opens directly.
- SQLite therefore enforces the declared FOREIGN KEY constraints on repository writes that use `connect()`.

## Tenant ownership of recommendation references

Before insert, `insert_recommendation()` validates that each provided reference exists **and** belongs to the same `tenant_id`:

- `portfolio_snapshot_id`
- `market_quote_snapshot_id`
- `supersedes_recommendation_id`

Missing or cross-tenant references raise **`ValueError`**. Tenant A cannot attach Tenant B’s snapshot or recommendation IDs even when the numeric/text ID exists.

## Snapshot insert-or-get (conflict-safe)

Portfolio and market-quote snapshots are content-addressed by `(tenant_id, snapshot_hash)`:

1. SELECT existing row.
2. INSERT if missing.
3. On `UNIQUE` conflict (`sqlite3.IntegrityError`), roll back the insert attempt, re-SELECT, and return the existing row.

Duplicate snapshot inserts therefore return the existing row rather than raising.

## Recommendations (append-only)

- Duplicate `recommendation_id` still raises **`sqlite3.IntegrityError`**.
- Corrections use `supersedes_recommendation_id` (no UPDATE of business fields).

## Hash contracts

### Portfolio snapshot hash (`ps_*`)

**Includes:** tenant_id, base_currency, holdings sorted by symbol (symbol, quantity, avg_cost), cash, buying_power, total_equity, optional risk_state, schema version.  
**Excludes:** captured_at, UI labels, secrets.

### Market quote snapshot hash (`mqs_*`)

**Includes:** tenant_id, symbol, asset_type, provider, as_of, available_time, retrieved_at, bid/ask/last/volume, quality_state, schema version.

### Analysis context hash (`ctx_*`)

**Includes:** tenant_id, source, portfolio_snapshot_hash, ordered market quote hashes, AI provider/model, prompt_bundle_hash, config_hash, version_bundle, context schema version.  
**Excludes:** recommendation/AI output text, tokens, latency, hostnames, request IDs.

`context_hash` identifies **input context only**. It does not imply identical LLM output.

## Tenant model

- Every row requires non-empty `tenant_id`.
- Customers: auth `user_id` UUID string.
- Owner / daily-chain: `OWNER_TENANT_ID = "owner"` (never NULL).
- Getters always filter by `tenant_id`; cross-tenant lookups return `None`.

## Money precision

SQLite `REAL` for monetary columns (same convention as legacy paper tables). Canonical hashing preserves `Decimal` via a type tag when present in hash inputs. Binary float storage is not exact for all decimal values.

## Migration procedure

1. Deploy code containing `gesh_core.ledger` and the `init_db()` hook.
2. On startup, `init_db()` calls `init_ledger_tables()` (`CREATE TABLE/INDEX IF NOT EXISTS`).
3. Safe on empty and populated databases. No migration of legacy rows.

## Rollback procedure

1. Stop calling ledger repository helpers (none are wired into production paths in Phase 4A).
2. Empty tables may remain in place harmlessly.
3. Do **not** drop tables that may contain data without backup and an explicit operator decision.
4. Revert the `init_db()` ledger hook if desired.

## Compatibility guarantees

- No changes to `analysis_runs`, `equity_snapshots`, `paper_trades`, `trade_log`, or trading state tables beyond shared `connect()` enabling FK pragma.
- No changes to paper trading, risk gate, consensus, Kelly, or Monte Carlo behavior.
- Snapshots are content-addressed and conflict-safe.
- Recommendations are append-only.
