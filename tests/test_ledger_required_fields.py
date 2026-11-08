"""Repository write-boundary fail-closed checks left unpinned on main.

Hosts (and the integration layer) call these helpers directly. A blank
snapshot_hash / recommendation_id / context_hash / action must raise before a
row is written — otherwise the content-addressed ledger can persist an
unidentifiable decision. Whitespace-only tenant_id must also fail closed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gesh_core.ledger.repository import (
    get_portfolio_snapshot,
    get_recommendation,
    insert_or_get_market_quote_snapshot,
    insert_or_get_portfolio_snapshot,
    insert_recommendation,
)
from gesh_core.ledger.schema import init_ledger_tables
from gesh_core.ledger.versions import OWNER_TENANT_ID


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "ledger_required.db"
    init_ledger_tables(path)
    return path


@pytest.mark.parametrize("snapshot_hash", ["", None])
def test_portfolio_snapshot_requires_hash(db_path: Path, snapshot_hash):
    with pytest.raises(ValueError, match="snapshot_hash is required"):
        insert_or_get_portfolio_snapshot(
            tenant_id=OWNER_TENANT_ID,
            snapshot_hash=snapshot_hash,
            holdings=[{"symbol": "AAPL", "quantity": 1}],
            cash=0.0,
            buying_power=0.0,
            total_equity=1.0,
            db_path=db_path,
        )


@pytest.mark.parametrize("snapshot_hash", ["", None])
def test_market_quote_snapshot_requires_hash(db_path: Path, snapshot_hash):
    with pytest.raises(ValueError, match="snapshot_hash is required"):
        insert_or_get_market_quote_snapshot(
            tenant_id=OWNER_TENANT_ID,
            snapshot_hash=snapshot_hash,
            symbol="NVDA",
            quality_state="FRESH",
            bid=1.0,
            ask=1.1,
            last=1.05,
            provider="test",
            as_of="2026-08-31T12:00:00Z",
            db_path=db_path,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("recommendation_id", ""),
        ("recommendation_id", None),
        ("context_hash", ""),
        ("context_hash", None),
        ("action", ""),
        ("action", None),
    ],
)
def test_recommendation_requires_identity_fields(db_path: Path, field: str, value):
    kwargs = {
        "recommendation_id": "rec_ok",
        "tenant_id": OWNER_TENANT_ID,
        "symbol": "NVDA",
        "context_hash": "ctx_ok",
        "decision_at": "2026-08-31T12:00:00Z",
        "source": "test",
        "action": "HOLD",
        "db_path": db_path,
    }
    kwargs[field] = value
    with pytest.raises(ValueError, match=f"{field} is required"):
        insert_recommendation(**kwargs)


def test_whitespace_tenant_id_is_rejected_on_reads(db_path: Path):
    with pytest.raises(ValueError, match="tenant_id"):
        get_portfolio_snapshot(1, tenant_id="   ", db_path=db_path)
    with pytest.raises(ValueError, match="tenant_id"):
        get_recommendation("rec_x", tenant_id="\t", db_path=db_path)
