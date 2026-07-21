"""Tests for ledger schema migration and tenant-scoped repository helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gesh_core.db import connect
from gesh_core.ledger.hashes import (
    analysis_context_hash,
    market_quote_snapshot_hash,
    portfolio_snapshot_hash,
)
from gesh_core.ledger.repository import (
    get_market_quote_snapshot,
    get_portfolio_snapshot,
    get_recommendation,
    insert_or_get_market_quote_snapshot,
    insert_or_get_portfolio_snapshot,
    insert_recommendation,
    list_recommendations,
)
from gesh_core.ledger.schema import init_ledger_tables
from gesh_core.ledger.versions import OWNER_TENANT_ID


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "ledger_test.db"
    init_ledger_tables(path)
    return path


def test_schema_initialization_idempotent(db_path: Path):
    init_ledger_tables(db_path)
    init_ledger_tables(db_path)
    with sqlite3.connect(db_path) as con:
        names = {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "portfolio_snapshots" in names
    assert "market_quote_snapshots" in names
    assert "recommendations" in names


def test_preserves_legacy_tables(tmp_path: Path):
    path = tmp_path / "with_legacy.db"
    with sqlite3.connect(path) as con:
        con.execute(
            "CREATE TABLE analysis_runs (id INTEGER PRIMARY KEY, run_at TEXT)"
        )
        con.execute("INSERT INTO analysis_runs (run_at) VALUES ('2026-01-01')")
        con.execute(
            "CREATE TABLE paper_trades (id INTEGER PRIMARY KEY, symbol TEXT)"
        )
        con.execute("INSERT INTO paper_trades (symbol) VALUES ('NVDA')")
        con.commit()
    init_ledger_tables(path)
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0] == 1


def test_connect_enables_foreign_keys(db_path: Path):
    with connect(db_path) as con:
        enabled = con.execute("PRAGMA foreign_keys").fetchone()[0]
    assert enabled == 1


def test_sqlite_fk_enforcement_rejects_nonexistent_snapshot(db_path: Path):
    """Direct SQL insert with a nonexistent FK must raise under PRAGMA foreign_keys=ON."""
    with connect(db_path) as con:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                """
                INSERT INTO recommendations (
                    recommendation_id, tenant_id, symbol, context_hash,
                    decision_at, source, action, portfolio_snapshot_id,
                    schema_version, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "rec_sql_fk_bad",
                    OWNER_TENANT_ID,
                    "X",
                    "ctx",
                    "2026-07-21T12:00:00Z",
                    "test",
                    "HOLD",
                    999999,
                    1,
                    "2026-07-21T12:00:00Z",
                ),
            )


def test_portfolio_insert_get_dedup_and_tenant_isolation(db_path: Path):
    holdings = [{"symbol": "AAPL", "quantity": 3, "avg_cost": 150.0}]
    h = portfolio_snapshot_hash(
        tenant_id=OWNER_TENANT_ID,
        holdings=holdings,
        cash=1000.0,
        buying_power=1000.0,
        total_equity=1450.0,
    )
    r1 = insert_or_get_portfolio_snapshot(
        tenant_id=OWNER_TENANT_ID,
        snapshot_hash=h,
        holdings=holdings,
        cash=1000.0,
        buying_power=1000.0,
        total_equity=1450.0,
        db_path=db_path,
    )
    r2 = insert_or_get_portfolio_snapshot(
        tenant_id=OWNER_TENANT_ID,
        snapshot_hash=h,
        holdings=holdings,
        cash=1000.0,
        buying_power=1000.0,
        total_equity=1450.0,
        db_path=db_path,
    )
    assert r1["id"] == r2["id"]

    other = insert_or_get_portfolio_snapshot(
        tenant_id="customer-uuid-1",
        snapshot_hash=h,
        holdings=holdings,
        cash=1000.0,
        buying_power=1000.0,
        total_equity=1450.0,
        db_path=db_path,
    )
    assert other["tenant_id"] == "customer-uuid-1"
    assert other["id"] != r1["id"]

    assert get_portfolio_snapshot(
        r1["id"], tenant_id=OWNER_TENANT_ID, db_path=db_path
    )
    assert (
        get_portfolio_snapshot(
            r1["id"], tenant_id="customer-uuid-1", db_path=db_path
        )
        is None
    )


def test_duplicate_portfolio_snapshot_returns_existing(db_path: Path):
    holdings = [{"symbol": "TSLA", "quantity": 1}]
    h = portfolio_snapshot_hash(
        tenant_id=OWNER_TENANT_ID,
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=1.0,
    )
    first = insert_or_get_portfolio_snapshot(
        tenant_id=OWNER_TENANT_ID,
        snapshot_hash=h,
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=1.0,
        db_path=db_path,
    )
    second = insert_or_get_portfolio_snapshot(
        tenant_id=OWNER_TENANT_ID,
        snapshot_hash=h,
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=1.0,
        db_path=db_path,
    )
    assert second["id"] == first["id"]


def test_duplicate_market_quote_snapshot_returns_existing(db_path: Path):
    mq_hash = market_quote_snapshot_hash(
        tenant_id=OWNER_TENANT_ID,
        symbol="NVDA",
        provider="yahoo",
        as_of="2026-07-21T14:00:00Z",
        bid=120.0,
        ask=120.1,
        last=120.05,
        quality_state="FRESH",
    )
    first = insert_or_get_market_quote_snapshot(
        tenant_id=OWNER_TENANT_ID,
        snapshot_hash=mq_hash,
        symbol="NVDA",
        provider="yahoo",
        as_of="2026-07-21T14:00:00Z",
        bid=120.0,
        ask=120.1,
        last=120.05,
        quality_state="FRESH",
        db_path=db_path,
    )
    second = insert_or_get_market_quote_snapshot(
        tenant_id=OWNER_TENANT_ID,
        snapshot_hash=mq_hash,
        symbol="NVDA",
        provider="yahoo",
        as_of="2026-07-21T14:00:00Z",
        bid=120.0,
        ask=120.1,
        last=120.05,
        quality_state="FRESH",
        db_path=db_path,
    )
    assert second["id"] == first["id"]


def test_market_quote_invalid_quality_rejected(db_path: Path):
    with pytest.raises(ValueError, match="quality_state"):
        insert_or_get_market_quote_snapshot(
            tenant_id=OWNER_TENANT_ID,
            snapshot_hash="mqs_bad",
            symbol="X",
            quality_state="UNKNOWN",
            bid=1.0,
            ask=1.0,
            last=1.0,
            provider="test",
            as_of="2026-07-21T00:00:00Z",
            db_path=db_path,
        )


def test_recommendation_roundtrip_duplicate_and_list(db_path: Path):
    holdings = [{"symbol": "NVDA", "quantity": 1}]
    ps_hash = portfolio_snapshot_hash(
        tenant_id=OWNER_TENANT_ID,
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=100.0,
    )
    ps = insert_or_get_portfolio_snapshot(
        tenant_id=OWNER_TENANT_ID,
        snapshot_hash=ps_hash,
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=100.0,
        db_path=db_path,
    )
    mq_hash = market_quote_snapshot_hash(
        tenant_id=OWNER_TENANT_ID,
        symbol="NVDA",
        provider="yahoo",
        as_of="2026-07-21T14:00:00Z",
        bid=120.0,
        ask=120.1,
        last=120.05,
        quality_state="FRESH",
    )
    mq = insert_or_get_market_quote_snapshot(
        tenant_id=OWNER_TENANT_ID,
        snapshot_hash=mq_hash,
        symbol="NVDA",
        provider="yahoo",
        as_of="2026-07-21T14:00:00Z",
        bid=120.0,
        ask=120.1,
        last=120.05,
        quality_state="FRESH",
        db_path=db_path,
    )
    ctx = analysis_context_hash(
        tenant_id=OWNER_TENANT_ID,
        source="daily-chain",
        portfolio_snapshot_hash_value=ps_hash,
        market_quote_snapshot_hashes=[mq_hash],
    )
    rec = insert_recommendation(
        recommendation_id="rec_test_001",
        tenant_id=OWNER_TENANT_ID,
        symbol="NVDA",
        context_hash=ctx,
        decision_at="2026-07-21T14:05:00Z",
        source="daily-chain",
        action="HOLD",
        portfolio_snapshot_id=ps["id"],
        market_quote_snapshot_id=mq["id"],
        conviction=0.4,
        confidence=0.55,
        consensus={"score": 0.1},
        quant_summary={"kelly": 0.0},
        db_path=db_path,
    )
    assert rec["recommendation_id"] == "rec_test_001"
    assert rec["intent_id"] is None

    got = get_recommendation(
        "rec_test_001", tenant_id=OWNER_TENANT_ID, db_path=db_path
    )
    assert got is not None
    assert got["action"] == "HOLD"
    assert (
        get_recommendation("rec_test_001", tenant_id="other-tenant", db_path=db_path)
        is None
    )

    with pytest.raises(sqlite3.IntegrityError):
        insert_recommendation(
            recommendation_id="rec_test_001",
            tenant_id=OWNER_TENANT_ID,
            symbol="NVDA",
            context_hash=ctx,
            decision_at="2026-07-21T14:06:00Z",
            source="daily-chain",
            action="BUY",
            db_path=db_path,
        )

    insert_recommendation(
        recommendation_id="rec_test_002",
        tenant_id=OWNER_TENANT_ID,
        symbol="AAPL",
        context_hash=ctx,
        decision_at="2026-07-22T10:00:00Z",
        source="daily-chain",
        action="BUY",
        db_path=db_path,
    )
    listed = list_recommendations(
        tenant_id=OWNER_TENANT_ID, limit=10, db_path=db_path
    )
    assert len(listed) == 2
    assert listed[0]["recommendation_id"] == "rec_test_002"

    limited = list_recommendations(
        tenant_id=OWNER_TENANT_ID, limit=1, db_path=db_path
    )
    assert len(limited) == 1

    by_symbol = list_recommendations(
        tenant_id=OWNER_TENANT_ID, symbol="nvda", db_path=db_path
    )
    assert len(by_symbol) == 1
    assert by_symbol[0]["symbol"] == "NVDA"


def test_valid_same_tenant_snapshot_references_succeed(db_path: Path):
    holdings = [{"symbol": "MSFT", "quantity": 1}]
    ps_h = portfolio_snapshot_hash(
        tenant_id=OWNER_TENANT_ID,
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=50.0,
    )
    ps = insert_or_get_portfolio_snapshot(
        tenant_id=OWNER_TENANT_ID,
        snapshot_hash=ps_h,
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=50.0,
        db_path=db_path,
    )
    mq_h = market_quote_snapshot_hash(
        tenant_id=OWNER_TENANT_ID,
        symbol="MSFT",
        provider="yahoo",
        as_of="2026-07-21T12:00:00Z",
        bid=10.0,
        ask=10.1,
        last=10.05,
        quality_state="FRESH",
    )
    mq = insert_or_get_market_quote_snapshot(
        tenant_id=OWNER_TENANT_ID,
        snapshot_hash=mq_h,
        symbol="MSFT",
        provider="yahoo",
        as_of="2026-07-21T12:00:00Z",
        bid=10.0,
        ask=10.1,
        last=10.05,
        quality_state="FRESH",
        db_path=db_path,
    )
    ctx = analysis_context_hash(
        tenant_id=OWNER_TENANT_ID,
        source="test",
        portfolio_snapshot_hash_value=ps_h,
    )
    rec = insert_recommendation(
        recommendation_id="rec_fk_ok",
        tenant_id=OWNER_TENANT_ID,
        symbol="MSFT",
        context_hash=ctx,
        decision_at="2026-07-21T12:00:00Z",
        source="test",
        action="HOLD",
        portfolio_snapshot_id=ps["id"],
        market_quote_snapshot_id=mq["id"],
        db_path=db_path,
    )
    assert rec["portfolio_snapshot_id"] == ps["id"]
    assert rec["market_quote_snapshot_id"] == mq["id"]


def test_invalid_portfolio_snapshot_id_raises_value_error(db_path: Path):
    ctx = analysis_context_hash(
        tenant_id=OWNER_TENANT_ID,
        source="test",
        portfolio_snapshot_hash_value="ps_x",
    )
    with pytest.raises(ValueError, match="portfolio_snapshot_id"):
        insert_recommendation(
            recommendation_id="rec_bad_ps",
            tenant_id=OWNER_TENANT_ID,
            symbol="X",
            context_hash=ctx,
            decision_at="2026-07-21T12:00:00Z",
            source="test",
            action="HOLD",
            portfolio_snapshot_id=999999,
            db_path=db_path,
        )


def test_invalid_market_quote_snapshot_id_raises_value_error(db_path: Path):
    ctx = analysis_context_hash(
        tenant_id=OWNER_TENANT_ID,
        source="test",
        portfolio_snapshot_hash_value="ps_x",
    )
    with pytest.raises(ValueError, match="market_quote_snapshot_id"):
        insert_recommendation(
            recommendation_id="rec_bad_mq",
            tenant_id=OWNER_TENANT_ID,
            symbol="X",
            context_hash=ctx,
            decision_at="2026-07-21T12:00:00Z",
            source="test",
            action="HOLD",
            market_quote_snapshot_id=999999,
            db_path=db_path,
        )


def test_cross_tenant_portfolio_snapshot_raises_value_error(db_path: Path):
    holdings = [{"symbol": "AAPL", "quantity": 1}]
    h = portfolio_snapshot_hash(
        tenant_id="tenant-a",
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=1.0,
    )
    ps = insert_or_get_portfolio_snapshot(
        tenant_id="tenant-a",
        snapshot_hash=h,
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=1.0,
        db_path=db_path,
    )
    ctx = analysis_context_hash(
        tenant_id="tenant-b",
        source="test",
        portfolio_snapshot_hash_value="ps_y",
    )
    with pytest.raises(ValueError, match="belongs to tenant"):
        insert_recommendation(
            recommendation_id="rec_xt_ps",
            tenant_id="tenant-b",
            symbol="AAPL",
            context_hash=ctx,
            decision_at="2026-07-21T12:00:00Z",
            source="test",
            action="HOLD",
            portfolio_snapshot_id=ps["id"],
            db_path=db_path,
        )


def test_cross_tenant_market_quote_raises_value_error(db_path: Path):
    mq_h = market_quote_snapshot_hash(
        tenant_id="tenant-a",
        symbol="AAPL",
        provider="yahoo",
        as_of="2026-07-21T12:00:00Z",
        bid=1.0,
        ask=1.1,
        last=1.05,
        quality_state="FRESH",
    )
    mq = insert_or_get_market_quote_snapshot(
        tenant_id="tenant-a",
        snapshot_hash=mq_h,
        symbol="AAPL",
        provider="yahoo",
        as_of="2026-07-21T12:00:00Z",
        bid=1.0,
        ask=1.1,
        last=1.05,
        quality_state="FRESH",
        db_path=db_path,
    )
    ctx = analysis_context_hash(
        tenant_id="tenant-b",
        source="test",
        portfolio_snapshot_hash_value="ps_y",
    )
    with pytest.raises(ValueError, match="belongs to tenant"):
        insert_recommendation(
            recommendation_id="rec_xt_mq",
            tenant_id="tenant-b",
            symbol="AAPL",
            context_hash=ctx,
            decision_at="2026-07-21T12:00:00Z",
            source="test",
            action="HOLD",
            market_quote_snapshot_id=mq["id"],
            db_path=db_path,
        )


def test_cross_tenant_supersedes_raises_value_error(db_path: Path):
    ctx_a = analysis_context_hash(
        tenant_id="tenant-a",
        source="manual",
        portfolio_snapshot_hash_value="ps_a",
    )
    insert_recommendation(
        recommendation_id="rec_a_only",
        tenant_id="tenant-a",
        symbol="AAPL",
        context_hash=ctx_a,
        decision_at="2026-07-20T10:00:00Z",
        source="manual",
        action="HOLD",
        db_path=db_path,
    )
    ctx_b = analysis_context_hash(
        tenant_id="tenant-b",
        source="manual",
        portfolio_snapshot_hash_value="ps_b",
    )
    with pytest.raises(ValueError, match="belongs to tenant"):
        insert_recommendation(
            recommendation_id="rec_b_bad",
            tenant_id="tenant-b",
            symbol="AAPL",
            context_hash=ctx_b,
            decision_at="2026-07-21T10:00:00Z",
            source="manual",
            action="BUY",
            supersedes_recommendation_id="rec_a_only",
            db_path=db_path,
        )


def test_valid_same_tenant_supersedes_succeeds(db_path: Path):
    ctx = analysis_context_hash(
        tenant_id=OWNER_TENANT_ID,
        source="manual",
        portfolio_snapshot_hash_value="ps_x",
    )
    insert_recommendation(
        recommendation_id="rec_a",
        tenant_id=OWNER_TENANT_ID,
        symbol="AAPL",
        context_hash=ctx,
        decision_at="2026-07-20T10:00:00Z",
        source="manual",
        action="HOLD",
        db_path=db_path,
    )
    insert_recommendation(
        recommendation_id="rec_b",
        tenant_id=OWNER_TENANT_ID,
        symbol="AAPL",
        context_hash=ctx,
        decision_at="2026-07-21T10:00:00Z",
        source="manual",
        action="BUY",
        supersedes_recommendation_id="rec_a",
        db_path=db_path,
    )
    b = get_recommendation("rec_b", tenant_id=OWNER_TENANT_ID, db_path=db_path)
    assert b is not None
    assert b["supersedes_recommendation_id"] == "rec_a"


def test_tenant_required(db_path: Path):
    with pytest.raises(ValueError, match="tenant_id"):
        insert_or_get_portfolio_snapshot(
            tenant_id="",
            snapshot_hash="ps_x",
            holdings=[],
            db_path=db_path,
        )
