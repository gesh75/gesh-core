"""``list_recommendations`` clamps ``limit`` into ``[1, 500]``.

``limit=0`` would otherwise emit ``LIMIT 0`` (empty page that looks like
"no decisions"). Pin the lower clamp; the 500 ceiling is the matching
upper bound in the same expression.
"""

from __future__ import annotations

from pathlib import Path

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

TENANT = "owner"


def _seed(db_path: Path, n: int) -> None:
    init_ledger_tables(db_path)
    holdings = [{"symbol": "NVDA", "quantity": 1, "avg_cost": 1.0}]
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
        db_path=db_path,
    )
    q_hash = market_quote_snapshot_hash(
        tenant_id=TENANT,
        symbol="NVDA",
        provider=None,
        as_of=None,
        bid=None,
        ask=None,
        last=1.0,
        quality_state="FRESH",
    )
    mqs = insert_or_get_market_quote_snapshot(
        tenant_id=TENANT,
        snapshot_hash=q_hash,
        symbol="NVDA",
        quality_state="FRESH",
        last=1.0,
        db_path=db_path,
    )
    ctx = analysis_context_hash(
        tenant_id=TENANT,
        source="test",
        portfolio_snapshot_hash_value=ps_hash,
        market_quote_snapshot_hashes=[q_hash],
    )
    for i in range(n):
        insert_recommendation(
            recommendation_id=f"rec-{i:03d}",
            tenant_id=TENANT,
            symbol="NVDA",
            context_hash=ctx,
            decision_at=f"2026-08-0{(i % 9) + 1}T00:00:00Z",
            source="test",
            action="HOLD",
            portfolio_snapshot_id=ps["id"],
            market_quote_snapshot_id=mqs["id"],
            db_path=db_path,
        )


def test_zero_limit_returns_one_row_not_empty(tmp_path):
    db_path = tmp_path / "ledger.db"
    _seed(db_path, 3)
    rows = list_recommendations(tenant_id=TENANT, limit=0, db_path=db_path)
    assert len(rows) == 1
