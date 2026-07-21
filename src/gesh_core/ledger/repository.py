"""Tenant-scoped data-access helpers for Decision Ledger tables (Phase 4A).

Snapshots are content-addressed (tenant_id + snapshot_hash) and idempotent.
Recommendations are append-only; duplicate recommendation_id is rejected.
No generic UPDATE helpers for immutable business fields are provided.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from gesh_core.db import connect
from gesh_core.db_path import resolve_db_path
from gesh_core.ledger.schema import init_ledger_tables
from gesh_core.ledger.versions import (
    MARKET_QUOTE_SNAPSHOT_SCHEMA_VERSION,
    PORTFOLIO_SNAPSHOT_SCHEMA_VERSION,
    RECOMMENDATION_SCHEMA_VERSION,
)

_QUALITY_STATES = frozenset({"FRESH", "STALE", "DEGRADED", "MISSING", "CONFLICTING"})


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _require_tenant(tenant_id: str) -> str:
    if not tenant_id or not str(tenant_id).strip():
        raise ValueError("tenant_id is required")
    return str(tenant_id).strip()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _require_same_tenant_row(
    con: sqlite3.Connection,
    *,
    table: str,
    id_column: str,
    row_id: Any,
    tenant_id: str,
    label: str,
) -> None:
    """Reject missing or cross-tenant foreign references with ValueError."""
    row = con.execute(
        f"SELECT tenant_id FROM {table} WHERE {id_column}=?",
        (row_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"{label} {row_id!r} does not exist")
    owner = row["tenant_id"] if isinstance(row, sqlite3.Row) else row[0]
    if owner != tenant_id:
        raise ValueError(f"{label} {row_id!r} belongs to tenant {owner!r}, not {tenant_id!r}")


def insert_or_get_portfolio_snapshot(
    *,
    tenant_id: str,
    snapshot_hash: str,
    holdings: list[dict[str, Any]] | list[Mapping[str, Any]],
    cash: float | None = None,
    buying_power: float | None = None,
    total_equity: float | None = None,
    base_currency: str = "USD",
    risk_state: Mapping[str, Any] | None = None,
    captured_at: str | None = None,
    db_path: Any | None = None,
) -> dict[str, Any]:
    """Insert portfolio snapshot or return existing row for (tenant, hash).

    Conflict-safe: concurrent writers that hit UNIQUE(tenant_id, snapshot_hash)
    re-select and return the existing row instead of raising.
    """
    tenant_id = _require_tenant(tenant_id)
    if not snapshot_hash:
        raise ValueError("snapshot_hash is required")
    init_ledger_tables(db_path)
    path = db_path if db_path is not None else resolve_db_path()
    captured = captured_at or _now()
    created = _now()
    holdings_json = _json_dumps(list(holdings))
    risk_json = _json_dumps(risk_state) if risk_state is not None else None

    with connect(path) as con:
        con.row_factory = sqlite3.Row
        existing = con.execute(
            "SELECT * FROM portfolio_snapshots WHERE tenant_id=? AND snapshot_hash=?",
            (tenant_id, snapshot_hash),
        ).fetchone()
        if existing:
            return dict(existing)
        try:
            cur = con.execute(
                """
                INSERT INTO portfolio_snapshots (
                    tenant_id, snapshot_hash, captured_at, base_currency,
                    total_equity, cash, buying_power, holdings_json,
                    risk_state_json, schema_version, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    tenant_id,
                    snapshot_hash,
                    captured,
                    base_currency,
                    total_equity,
                    cash,
                    buying_power,
                    holdings_json,
                    risk_json,
                    PORTFOLIO_SNAPSHOT_SCHEMA_VERSION,
                    created,
                ),
            )
            con.commit()
            row = con.execute(
                "SELECT * FROM portfolio_snapshots WHERE id=?", (cur.lastrowid,)
            ).fetchone()
            return dict(row)
        except sqlite3.IntegrityError:
            con.rollback()
            row = con.execute(
                "SELECT * FROM portfolio_snapshots WHERE tenant_id=? AND snapshot_hash=?",
                (tenant_id, snapshot_hash),
            ).fetchone()
            if row is None:
                raise
            return dict(row)


def get_portfolio_snapshot(
    snapshot_id: int, *, tenant_id: str, db_path: Any | None = None
) -> dict[str, Any] | None:
    tenant_id = _require_tenant(tenant_id)
    init_ledger_tables(db_path)
    path = db_path if db_path is not None else resolve_db_path()
    with connect(path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM portfolio_snapshots WHERE id=? AND tenant_id=?",
            (snapshot_id, tenant_id),
        ).fetchone()
    return _row_to_dict(row)


def insert_or_get_market_quote_snapshot(
    *,
    tenant_id: str,
    snapshot_hash: str,
    symbol: str,
    quality_state: str,
    asset_type: str = "equity",
    provider: str | None = None,
    as_of: str | None = None,
    available_time: str | None = None,
    retrieved_at: str | None = None,
    bid: float | None = None,
    ask: float | None = None,
    last: float | None = None,
    volume: float | None = None,
    quality_reason: str | None = None,
    payload: Mapping[str, Any] | None = None,
    db_path: Any | None = None,
) -> dict[str, Any]:
    """Insert market quote snapshot or return existing row for (tenant, hash).

    Conflict-safe under concurrent writers (UNIQUE tenant_id + snapshot_hash).
    """
    tenant_id = _require_tenant(tenant_id)
    if not snapshot_hash:
        raise ValueError("snapshot_hash is required")
    if quality_state not in _QUALITY_STATES:
        raise ValueError(f"invalid quality_state: {quality_state!r}")
    init_ledger_tables(db_path)
    path = db_path if db_path is not None else resolve_db_path()
    retrieved = retrieved_at or _now()
    created = _now()
    payload_json = _json_dumps(payload) if payload is not None else None

    with connect(path) as con:
        con.row_factory = sqlite3.Row
        existing = con.execute(
            "SELECT * FROM market_quote_snapshots WHERE tenant_id=? AND snapshot_hash=?",
            (tenant_id, snapshot_hash),
        ).fetchone()
        if existing:
            return dict(existing)
        try:
            cur = con.execute(
                """
                INSERT INTO market_quote_snapshots (
                    tenant_id, snapshot_hash, symbol, asset_type, provider,
                    as_of, available_time, retrieved_at, bid, ask, last, volume,
                    quality_state, quality_reason, payload_json, schema_version, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    tenant_id,
                    snapshot_hash,
                    symbol.upper(),
                    asset_type,
                    provider,
                    as_of,
                    available_time,
                    retrieved,
                    bid,
                    ask,
                    last,
                    volume,
                    quality_state,
                    quality_reason,
                    payload_json,
                    MARKET_QUOTE_SNAPSHOT_SCHEMA_VERSION,
                    created,
                ),
            )
            con.commit()
            row = con.execute(
                "SELECT * FROM market_quote_snapshots WHERE id=?", (cur.lastrowid,)
            ).fetchone()
            return dict(row)
        except sqlite3.IntegrityError:
            con.rollback()
            row = con.execute(
                "SELECT * FROM market_quote_snapshots WHERE tenant_id=? AND snapshot_hash=?",
                (tenant_id, snapshot_hash),
            ).fetchone()
            if row is None:
                raise
            return dict(row)


def get_market_quote_snapshot(
    snapshot_id: int, *, tenant_id: str, db_path: Any | None = None
) -> dict[str, Any] | None:
    tenant_id = _require_tenant(tenant_id)
    init_ledger_tables(db_path)
    path = db_path if db_path is not None else resolve_db_path()
    with connect(path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM market_quote_snapshots WHERE id=? AND tenant_id=?",
            (snapshot_id, tenant_id),
        ).fetchone()
    return _row_to_dict(row)


def insert_recommendation(
    *,
    recommendation_id: str,
    tenant_id: str,
    symbol: str,
    context_hash: str,
    decision_at: str,
    source: str,
    action: str,
    analysis_run_id: int | None = None,
    asset_type: str = "equity",
    portfolio_snapshot_id: int | None = None,
    market_quote_snapshot_id: int | None = None,
    conviction: float | None = None,
    confidence: float | None = None,
    target_position_pct: float | None = None,
    stop_price: float | None = None,
    target_price: float | None = None,
    consensus: Mapping[str, Any] | list[Any] | None = None,
    quant_summary: Mapping[str, Any] | None = None,
    ai_output: Mapping[str, Any] | None = None,
    ai_provider: str | None = None,
    ai_model: str | None = None,
    prompt_bundle_hash: str | None = None,
    intent_id: int | None = None,
    supersedes_recommendation_id: str | None = None,
    db_path: Any | None = None,
) -> dict[str, Any]:
    """Insert a recommendation. Raises IntegrityError on duplicate ID.

    Snapshot and supersedes references must exist and belong to the same tenant.
    """
    tenant_id = _require_tenant(tenant_id)
    if not recommendation_id:
        raise ValueError("recommendation_id is required")
    if not context_hash:
        raise ValueError("context_hash is required")
    if not action:
        raise ValueError("action is required")
    init_ledger_tables(db_path)
    path = db_path if db_path is not None else resolve_db_path()
    created = _now()

    with connect(path) as con:
        con.row_factory = sqlite3.Row
        if portfolio_snapshot_id is not None:
            _require_same_tenant_row(
                con,
                table="portfolio_snapshots",
                id_column="id",
                row_id=portfolio_snapshot_id,
                tenant_id=tenant_id,
                label="portfolio_snapshot_id",
            )
        if market_quote_snapshot_id is not None:
            _require_same_tenant_row(
                con,
                table="market_quote_snapshots",
                id_column="id",
                row_id=market_quote_snapshot_id,
                tenant_id=tenant_id,
                label="market_quote_snapshot_id",
            )
        if supersedes_recommendation_id is not None:
            _require_same_tenant_row(
                con,
                table="recommendations",
                id_column="recommendation_id",
                row_id=supersedes_recommendation_id,
                tenant_id=tenant_id,
                label="supersedes_recommendation_id",
            )
        con.execute(
            """
            INSERT INTO recommendations (
                recommendation_id, analysis_run_id, tenant_id, symbol, asset_type,
                context_hash, portfolio_snapshot_id, market_quote_snapshot_id,
                decision_at, source, action, conviction, confidence,
                target_position_pct, stop_price, target_price,
                consensus_json, quant_summary_json, ai_output_json,
                ai_provider, ai_model, prompt_bundle_hash, intent_id,
                schema_version, supersedes_recommendation_id, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                recommendation_id,
                analysis_run_id,
                tenant_id,
                symbol.upper(),
                asset_type,
                context_hash,
                portfolio_snapshot_id,
                market_quote_snapshot_id,
                decision_at,
                source,
                action,
                conviction,
                confidence,
                target_position_pct,
                stop_price,
                target_price,
                _json_dumps(consensus) if consensus is not None else None,
                _json_dumps(quant_summary) if quant_summary is not None else None,
                _json_dumps(ai_output) if ai_output is not None else None,
                ai_provider,
                ai_model,
                prompt_bundle_hash,
                intent_id,
                RECOMMENDATION_SCHEMA_VERSION,
                supersedes_recommendation_id,
                created,
            ),
        )
        con.commit()
        row = con.execute(
            "SELECT * FROM recommendations WHERE recommendation_id=?",
            (recommendation_id,),
        ).fetchone()
        return dict(row)


def get_recommendation(
    recommendation_id: str, *, tenant_id: str, db_path: Any | None = None
) -> dict[str, Any] | None:
    tenant_id = _require_tenant(tenant_id)
    init_ledger_tables(db_path)
    path = db_path if db_path is not None else resolve_db_path()
    with connect(path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM recommendations WHERE recommendation_id=? AND tenant_id=?",
            (recommendation_id, tenant_id),
        ).fetchone()
    return _row_to_dict(row)


def list_recommendations(
    *,
    tenant_id: str,
    limit: int = 50,
    before_decision_at: str | None = None,
    symbol: str | None = None,
    db_path: Any | None = None,
) -> list[dict[str, Any]]:
    """List recommendations for a tenant, newest decision_at first. Bounded."""
    tenant_id = _require_tenant(tenant_id)
    limit = max(1, min(int(limit), 500))
    init_ledger_tables(db_path)
    path = db_path if db_path is not None else resolve_db_path()

    clauses = ["tenant_id=?"]
    params: list[Any] = [tenant_id]
    if before_decision_at:
        clauses.append("decision_at < ?")
        params.append(before_decision_at)
    if symbol:
        clauses.append("symbol=?")
        params.append(symbol.upper())
    params.append(limit)

    sql = (
        "SELECT * FROM recommendations WHERE "
        + " AND ".join(clauses)
        + " ORDER BY decision_at DESC, recommendation_id DESC LIMIT ?"
    )
    with connect(path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
