"""Bounded recommendation reads: ``before_decision_at`` cursor pagination.

Dashboards page history newest-first. A broken cursor either skips a row
(silent audit gap) or repeats one (duplicate alerts).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gesh_core.ledger.hashes import (
    analysis_context_hash,
    market_quote_snapshot_hash,
    portfolio_snapshot_hash,
)
from gesh_core.ledger.repository import (
    insert_or_get_market_quote_snapshot,
    insert_or_get_portfolio_snapshot,
    insert_recommendation,
    list_recommendations,
)
from gesh_core.ledger.schema import init_ledger_tables

OWNER = "owner"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "ledger_cursor.db"
    init_ledger_tables(path)
    return path


def _seed_context(db_path: Path) -> tuple[str, int, int]:
    holdings = [{"symbol": "NVDA", "quantity": 1}]
    ps_hash = portfolio_snapshot_hash(
        tenant_id=OWNER,
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=100.0,
    )
    ps = insert_or_get_portfolio_snapshot(
        tenant_id=OWNER,
        snapshot_hash=ps_hash,
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=100.0,
        db_path=db_path,
    )
    mq_hash = market_quote_snapshot_hash(
        tenant_id=OWNER,
        symbol="NVDA",
        provider="yahoo",
        as_of="2026-07-21T14:00:00Z",
        bid=None,
        ask=None,
        last=120.0,
        quality_state="FRESH",
    )
    mq = insert_or_get_market_quote_snapshot(
        tenant_id=OWNER,
        snapshot_hash=mq_hash,
        symbol="NVDA",
        provider="yahoo",
        as_of="2026-07-21T14:00:00Z",
        bid=None,
        ask=None,
        last=120.0,
        quality_state="FRESH",
        db_path=db_path,
    )
    ctx = analysis_context_hash(
        tenant_id=OWNER,
        source="daily-chain",
        portfolio_snapshot_hash_value=ps_hash,
        market_quote_snapshot_hashes=[mq_hash],
    )
    return ctx, int(ps["id"]), int(mq["id"])


def _insert(
    db_path: Path,
    *,
    rid: str,
    symbol: str,
    decision_at: str,
    action: str,
    ctx: str,
    ps_id: int,
    mq_id: int,
) -> None:
    insert_recommendation(
        recommendation_id=rid,
        tenant_id=OWNER,
        symbol=symbol,
        context_hash=ctx,
        decision_at=decision_at,
        source="daily-chain",
        action=action,
        portfolio_snapshot_id=ps_id,
        market_quote_snapshot_id=mq_id,
        db_path=db_path,
    )


def test_before_decision_at_excludes_cursor_row_and_newer(db_path: Path) -> None:
    ctx, ps_id, mq_id = _seed_context(db_path)
    t1, t2, t3 = "2026-07-21T10:00:00Z", "2026-07-21T11:00:00Z", "2026-07-21T12:00:00Z"
    _insert(
        db_path,
        rid="rec_t1",
        symbol="NVDA",
        decision_at=t1,
        action="HOLD",
        ctx=ctx,
        ps_id=ps_id,
        mq_id=mq_id,
    )
    _insert(
        db_path,
        rid="rec_t2",
        symbol="AAPL",
        decision_at=t2,
        action="BUY",
        ctx=ctx,
        ps_id=ps_id,
        mq_id=mq_id,
    )
    _insert(
        db_path,
        rid="rec_t3",
        symbol="NVDA",
        decision_at=t3,
        action="SELL",
        ctx=ctx,
        ps_id=ps_id,
        mq_id=mq_id,
    )

    newest = list_recommendations(tenant_id=OWNER, limit=10, db_path=db_path)
    assert [r["recommendation_id"] for r in newest] == ["rec_t3", "rec_t2", "rec_t1"]

    page = list_recommendations(tenant_id=OWNER, limit=10, before_decision_at=t3, db_path=db_path)
    assert [r["recommendation_id"] for r in page] == ["rec_t2", "rec_t1"]

    last = list_recommendations(tenant_id=OWNER, limit=10, before_decision_at=t2, db_path=db_path)
    assert [r["recommendation_id"] for r in last] == ["rec_t1"]


def test_cursor_and_symbol_filter_combine(db_path: Path) -> None:
    ctx, ps_id, mq_id = _seed_context(db_path)
    _insert(
        db_path,
        rid="rec_a1",
        symbol="NVDA",
        decision_at="2026-07-21T10:00:00Z",
        action="HOLD",
        ctx=ctx,
        ps_id=ps_id,
        mq_id=mq_id,
    )
    _insert(
        db_path,
        rid="rec_b1",
        symbol="AAPL",
        decision_at="2026-07-21T11:00:00Z",
        action="BUY",
        ctx=ctx,
        ps_id=ps_id,
        mq_id=mq_id,
    )
    _insert(
        db_path,
        rid="rec_a2",
        symbol="nvda",
        decision_at="2026-07-21T12:00:00Z",
        action="SELL",
        ctx=ctx,
        ps_id=ps_id,
        mq_id=mq_id,
    )

    page = list_recommendations(
        tenant_id=OWNER,
        symbol="nvda",
        before_decision_at="2026-07-21T12:00:00Z",
        limit=10,
        db_path=db_path,
    )
    assert [r["recommendation_id"] for r in page] == ["rec_a1"]
    assert page[0]["symbol"] == "NVDA"


def test_limit_is_clamped_to_at_least_one(db_path: Path) -> None:
    ctx, ps_id, mq_id = _seed_context(db_path)
    _insert(
        db_path,
        rid="rec_1",
        symbol="NVDA",
        decision_at="2026-07-21T10:00:00Z",
        action="HOLD",
        ctx=ctx,
        ps_id=ps_id,
        mq_id=mq_id,
    )
    _insert(
        db_path,
        rid="rec_2",
        symbol="AAPL",
        decision_at="2026-07-21T11:00:00Z",
        action="BUY",
        ctx=ctx,
        ps_id=ps_id,
        mq_id=mq_id,
    )
    listed = list_recommendations(tenant_id=OWNER, limit=0, db_path=db_path)
    assert len(listed) == 1
    assert listed[0]["recommendation_id"] == "rec_2"
