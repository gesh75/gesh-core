"""Additive SQLite DDL for Decision Ledger tables (Phase 4A).

All statements are CREATE TABLE / INDEX IF NOT EXISTS. Safe to run repeatedly
against populated databases. Does not alter or migrate legacy tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from gesh_core.db_path import resolve_db_path

LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id         TEXT    NOT NULL,
    snapshot_hash     TEXT    NOT NULL,
    captured_at       TEXT    NOT NULL,
    base_currency     TEXT    NOT NULL DEFAULT 'USD',
    total_equity      REAL,
    cash              REAL,
    buying_power      REAL,
    holdings_json     TEXT    NOT NULL,
    risk_state_json   TEXT,
    schema_version    INTEGER NOT NULL,
    created_at        TEXT    NOT NULL,
    UNIQUE (tenant_id, snapshot_hash)
);

CREATE INDEX IF NOT EXISTS idx_ps_tenant_captured
    ON portfolio_snapshots (tenant_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_ps_hash
    ON portfolio_snapshots (snapshot_hash);

CREATE TABLE IF NOT EXISTS market_quote_snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id         TEXT    NOT NULL,
    snapshot_hash     TEXT    NOT NULL,
    symbol            TEXT    NOT NULL,
    asset_type        TEXT    NOT NULL DEFAULT 'equity',
    provider          TEXT,
    as_of             TEXT,
    available_time    TEXT,
    retrieved_at      TEXT    NOT NULL,
    bid               REAL,
    ask               REAL,
    last              REAL,
    volume            REAL,
    quality_state     TEXT    NOT NULL,
    quality_reason    TEXT,
    payload_json      TEXT,
    schema_version    INTEGER NOT NULL,
    created_at        TEXT    NOT NULL,
    UNIQUE (tenant_id, snapshot_hash),
    CHECK (quality_state IN ('FRESH', 'STALE', 'DEGRADED', 'MISSING', 'CONFLICTING'))
);

CREATE INDEX IF NOT EXISTS idx_mqs_tenant_symbol
    ON market_quote_snapshots (tenant_id, symbol, retrieved_at);
CREATE INDEX IF NOT EXISTS idx_mqs_hash
    ON market_quote_snapshots (snapshot_hash);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id              TEXT    PRIMARY KEY,
    analysis_run_id                INTEGER,
    tenant_id                      TEXT    NOT NULL,
    symbol                         TEXT    NOT NULL,
    asset_type                     TEXT    NOT NULL DEFAULT 'equity',
    context_hash                   TEXT    NOT NULL,
    portfolio_snapshot_id          INTEGER,
    market_quote_snapshot_id       INTEGER,
    decision_at                    TEXT    NOT NULL,
    source                         TEXT    NOT NULL,
    action                         TEXT    NOT NULL,
    conviction                     REAL,
    confidence                     REAL,
    target_position_pct            REAL,
    stop_price                     REAL,
    target_price                   REAL,
    consensus_json                 TEXT,
    quant_summary_json             TEXT,
    ai_output_json                 TEXT,
    ai_provider                    TEXT,
    ai_model                       TEXT,
    prompt_bundle_hash             TEXT,
    intent_id                      INTEGER,
    schema_version                 INTEGER NOT NULL,
    supersedes_recommendation_id   TEXT,
    created_at                     TEXT    NOT NULL,
    FOREIGN KEY (portfolio_snapshot_id)
        REFERENCES portfolio_snapshots(id),
    FOREIGN KEY (market_quote_snapshot_id)
        REFERENCES market_quote_snapshots(id),
    FOREIGN KEY (supersedes_recommendation_id)
        REFERENCES recommendations(recommendation_id)
);

CREATE INDEX IF NOT EXISTS idx_rec_tenant_decision
    ON recommendations (tenant_id, decision_at);
CREATE INDEX IF NOT EXISTS idx_rec_symbol
    ON recommendations (tenant_id, symbol, decision_at);
CREATE INDEX IF NOT EXISTS idx_rec_context
    ON recommendations (context_hash);
CREATE INDEX IF NOT EXISTS idx_rec_analysis_run
    ON recommendations (analysis_run_id);
"""


def init_ledger_tables(path: Any | None = None) -> None:
    """Ensure ledger tables exist. Safe to call repeatedly."""
    db_path = path if path is not None else resolve_db_path()
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=30000")
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(LEDGER_DDL)
        con.commit()
    finally:
        con.close()
