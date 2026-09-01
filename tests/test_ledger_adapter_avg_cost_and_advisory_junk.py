"""Daily-adapter leftover edges: avg_cost alias, advisory junk, non-positive prices.

The open adapter PR covers NaN cash and non-mapping holdings. These pin the
remaining fail-closed paths that would otherwise drop cost basis, crash on a
string in `portfolio_recommendations`, or mint a FRESH quote at $0.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from gesh_core.ledger.adapters.daily_analysis import record_daily_analysis_decision
from gesh_core.ledger.repository import get_portfolio_snapshot, get_recommendation
from gesh_core.ledger.schema import init_ledger_tables

TENANT = "owner"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "adapter_leftover.db"
    init_ledger_tables(path)
    return path


def _eng(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "holdings": [
            {
                "symbol": "NVDA",
                "quantity": 10,
                "avg_cost": 95.0,
                "current_price": 120.0,
            },
        ],
        "equity_summary": {"cash": 1000.0, "total": 2200.0},
        "consensus": {"NVDA": {"verdict": "HOLD", "confidence": 50.0}},
        "ai_result": {"holdings_analysis": [], "portfolio_recommendations": []},
        "ai_result_ran_at": "2026-07-20T09:30:00Z",
        "run_manifest": {"snapshot_as_of": "2026-07-20T09:00:00Z", "quote_as_of": {}},
        "snapshot": {"fetched_at": "2026-07-20T09:00:00Z"},
    }
    payload.update(overrides)
    return payload


def _record(db_path: Path, eng: dict[str, Any]) -> Any:
    return record_daily_analysis_decision(
        tenant_id=TENANT,
        source="daily_analysis_chain",
        engine_results=eng,
        analysis_run_id=1,
        ai_provider="anthropic",
        ai_model="claude-sonnet-4-6",
        db_path=db_path,
    )


def test_holding_avg_cost_used_when_average_buy_price_absent(db_path: Path) -> None:
    rec = _record(db_path, _eng()).recording
    ps = get_portfolio_snapshot(rec.portfolio_snapshot_id, tenant_id=TENANT, db_path=db_path)
    assert ps is not None
    holdings = json.loads(ps["holdings_json"])
    assert holdings[0]["avg_cost"] == 95.0
    assert "average_buy_price" not in holdings[0]


def test_non_mapping_advisory_items_are_skipped(db_path: Path) -> None:
    eng = _eng()
    eng["ai_result"]["portfolio_recommendations"] = [
        "not-a-row",
        None,
        {
            "action": "Consider adding",
            "category": "DIVERSIFICATION",
            "symbol": "MSFT",
            "rationale": "sector",
            "priority": "medium",
        },
    ]
    rec = _record(db_path, eng).recording
    symbols = []
    for rid in rec.recommendation_ids:
        row = get_recommendation(rid, tenant_id=TENANT, db_path=db_path)
        assert row is not None
        symbols.append(row["symbol"])
    assert "MSFT" in symbols
    assert symbols.count("NVDA") == 1


def test_non_positive_holding_price_is_missing_quote_not_fresh(db_path: Path) -> None:
    rec = _record(
        db_path,
        _eng(holdings=[{"symbol": "NVDA", "quantity": 10, "avg_cost": 95.0, "current_price": 0}]),
    ).recording
    nvda = get_recommendation(rec.recommendation_ids[0], tenant_id=TENANT, db_path=db_path)
    assert nvda is not None
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        quote = con.execute(
            "SELECT * FROM market_quote_snapshots WHERE id=?",
            (nvda["market_quote_snapshot_id"],),
        ).fetchone()
    assert quote is not None
    assert quote["quality_state"] == "MISSING"
    assert quote["last"] is None
