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

---

# Phase 4B addendum — recording orchestration

**Scope:** `gesh_core.ledger.integration` (generic `record_analysis_decision()`) and
`gesh_core.ledger.adapters.daily_analysis` (owner daily-analysis-chain adapter).
Still **no production caller** in this repo; the host wiring is a separate
`gesh-project` change.

## Persistence model

One recording persists exactly three kinds of objects, in order:

1. one `portfolio_snapshots` row (content-addressed, idempotent),
2. zero or more `market_quote_snapshots` rows (content-addressed, idempotent),
3. one or more `recommendations` rows (append-only).

The analysis context is **not a table and not a persisted object**: it is the
deterministic `ctx_*` hash stored on each recommendation (`context_hash` column).
There is no "insert analysis context" step anywhere in the workflow.

## Failure model

`record_analysis_decision()` either returns a successful `LedgerRecording` or
raises a `LedgerError` subclass (`LedgerValidationError`, `LedgerConflictError`,
`LedgerWriteError`). There is no `ok`/`error` result object; hosts that want
non-fatal ledger recording must catch at the call site.

## Recommendation identity

`recommendation_id = "rec_" + sha256(canonical_json(identity_payload))` where the
identity payload is `{schema_version, tenant_id, symbol, decision_type,
context_hash}` (full `ctx_*` value, nothing truncated; payload versioned by
`RECOMMENDATION_ID_SCHEMA_VERSION`, which is deliberately not part of
`version_bundle()`). Identity = (tenant, symbol, decision type, decision
context). `analysis_run_id` is optional provenance **metadata only** — never
part of the identity, and excluded from the idempotency fingerprint, so a
run-id-only difference on retry is idempotent. Its relationship to the legacy
`analysis_runs` table is **logical and unenforced** (no FK): it is meaningful
only when both sides resolve to the same `gesh_financial.db`.

## Partial writes and recovery

Writes commit per repository call; a recording is **not atomic** across rows.
Possible states after a failure:

| State | Persisted |
|---|---|
| S0 | nothing |
| S1 | portfolio snapshot only |
| S2 | portfolio + k of n quote snapshots |
| S3 | portfolio + n quotes + m of M recommendations (partial recommendation set) |
| S4 | complete |

Recovery: retry the same call with identical inputs. Snapshots dedup by
`(tenant_id, snapshot_hash)`; recommendations dedup by deterministic ID plus a
content fingerprint over the stored decision columns. Identical content →
idempotent reuse; same ID with different content → `LedgerConflictError`
(never silently treated as a duplicate). Retry converges to S4.

## Adapter contract (owner daily-analysis chain)

- Symbol universe: consensus verdicts (`action = verdict`) plus
  `portfolio_recommendations` items with `category == "DIVERSIFICATION"` and a
  valid symbol. Every exclusion is reported in `DailyAnalysisRecording.skipped`
  with a machine-readable reason — nothing is silently dropped.
- Field mapping: `average_buy_price → avg_cost`; holdings normalized to
  `{symbol, quantity, avg_cost, current_price}`; consensus/AI outputs pass
  through explicit key allowlists, so raw payloads are never canonicalized
  wholesale and secret-named keys are neither stored nor able to break hashing.
- Missing price: a decision symbol with no usable quote gets a
  `quality_state="MISSING"` quote snapshot with all price fields NULL and
  `retrieved_at` set — never a fabricated price.
- `tenant_id`, `source`, `ai_provider`, `ai_model` are explicit call-site
  arguments. The core assigns no default provenance and never infers a provider.
