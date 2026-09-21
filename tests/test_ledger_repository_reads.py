"""Read-path guards the open repository coverage PR does not claim.

list_recommendations(symbol=) is how the product pages a symbol's history.
A case-mismatch or missing-row raise would 500 the history endpoint.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gesh_core.ledger.hashes import market_quote_snapshot_hash, portfolio_snapshot_hash
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

TENANT = "owner"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "repo_reads.db"
    init_ledger_tables(path)
    return path


def _insert_rec(db_path: Path, symbol: str, decision_at: str) -> str:
    holdings = [{"symbol": symbol, "quantity": 1}]
    ps_hash = portfolio_snapshot_hash(
        tenant_id=TENANT,
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=1.0,
    )
    ps = insert_or_get_portfolio_snapshot(
        tenant_id=TENANT,
        snapshot_hash=ps_hash,
        holdings=holdings,
        cash=0.0,
        buying_power=0.0,
        total_equity=1.0,
        captured_at=decision_at,
        db_path=db_path,
    )
    rid = f"rec_read_{symbol.lower()}_{decision_at}"
    insert_recommendation(
        recommendation_id=rid,
        tenant_id=TENANT,
        symbol=symbol,
        context_hash="ctx_test",
        decision_at=decision_at,
        source="test",
        action="HOLD",
        portfolio_snapshot_id=int(ps["id"]),
        db_path=db_path,
    )
    return rid


def test_list_recommendations_filters_symbol_case_insensitively(db_path: Path):
    _insert_rec(db_path, "NVDA", "2026-07-20T09:00:00Z")
    _insert_rec(db_path, "AAPL", "2026-07-20T09:01:00Z")
    rows = list_recommendations(tenant_id=TENANT, symbol="nvda", db_path=db_path)
    assert [r["symbol"] for r in rows] == ["NVDA"]


def test_getters_return_none_for_missing_rows(db_path: Path):
    assert get_recommendation("rec_missing", tenant_id=TENANT, db_path=db_path) is None
    assert get_portfolio_snapshot(999_999, tenant_id=TENANT, db_path=db_path) is None
    assert get_market_quote_snapshot(999_999, tenant_id=TENANT, db_path=db_path) is None


def test_market_quote_get_roundtrip(db_path: Path):
    retrieved_at = "2026-07-20T09:00:01Z"
    mqs_hash = market_quote_snapshot_hash(
        tenant_id=TENANT,
        symbol="MSFT",
        provider="yahoo",
        as_of="2026-07-20T09:00:00Z",
        retrieved_at=retrieved_at,
        bid=1.0,
        ask=1.1,
        last=1.05,
        quality_state="FRESH",
    )
    row = insert_or_get_market_quote_snapshot(
        tenant_id=TENANT,
        snapshot_hash=mqs_hash,
        symbol="MSFT",
        quality_state="FRESH",
        provider="yahoo",
        as_of="2026-07-20T09:00:00Z",
        retrieved_at=retrieved_at,
        bid=1.0,
        ask=1.1,
        last=1.05,
        db_path=db_path,
    )
    fetched = get_market_quote_snapshot(int(row["id"]), tenant_id=TENANT, db_path=db_path)
    assert fetched is not None
    assert fetched["symbol"] == "MSFT"
    assert fetched["quality_state"] == "FRESH"
