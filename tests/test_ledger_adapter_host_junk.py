"""Host-payload junk the daily-adapter coverage PR does not claim.

Yahoo / engine snapshots regularly ship NaN cash, USD cash rows, and mixed
list contents. The adapter must coerce those without fabricating prices or
raising into the daily chain.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from gesh_core.ledger.adapters.daily_analysis import (
    SkippedDecision,
    record_daily_analysis_decision,
)
from gesh_core.ledger.repository import get_portfolio_snapshot, get_recommendation
from gesh_core.ledger.schema import init_ledger_tables

TENANT = "owner"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "adapter_junk.db"
    init_ledger_tables(path)
    return path


def _eng() -> dict[str, Any]:
    return {
        "holdings": [
            {
                "symbol": "NVDA",
                "quantity": 10,
                "average_buy_price": 100.0,
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


def test_nan_and_inf_equity_scalars_store_as_null(db_path: Path):
    eng = _eng()
    eng["equity_summary"] = {
        "cash": float("nan"),
        "buying_power": float("inf"),
        "total": float("-inf"),
    }
    rec = _record(db_path, eng).recording
    ps = get_portfolio_snapshot(rec.portfolio_snapshot_id, tenant_id=TENANT, db_path=db_path)
    assert ps is not None
    assert ps["cash"] is None
    assert ps["buying_power"] is None
    assert ps["total_equity"] is None


def test_total_equity_alias_used_when_total_absent(db_path: Path):
    eng = _eng()
    eng["equity_summary"] = {"cash": 250.0, "total_equity": 9_001.0}
    rec = _record(db_path, eng).recording
    ps = get_portfolio_snapshot(rec.portfolio_snapshot_id, tenant_id=TENANT, db_path=db_path)
    assert ps is not None
    assert ps["total_equity"] == pytest.approx(9001.0)
    assert ps["cash"] == pytest.approx(250.0)


def test_non_mapping_holdings_are_skipped(db_path: Path):
    eng = _eng()
    eng["holdings"].extend(["not-a-row", None, 42])
    rec = _record(db_path, eng).recording
    assert rec.recommendation_ids


def test_usd_consensus_symbol_is_cash_like(db_path: Path):
    eng = _eng()
    eng["consensus"]["USD"] = {"verdict": "HOLD"}
    result = _record(db_path, eng)
    assert (
        SkippedDecision(symbol="USD", decision_type="consensus", reason="cash_like_symbol")
        in result.skipped
    )
    symbols = []
    for rid in result.recording.recommendation_ids:
        row = get_recommendation(rid, tenant_id=TENANT, db_path=db_path)
        assert row is not None
        symbols.append(row["symbol"])
    assert "USD" not in symbols


def test_holding_price_alias_becomes_fresh_quote(db_path: Path):
    eng = _eng()
    eng["holdings"].append({"symbol": "GOOG", "quantity": 2, "price": 180.5})
    eng["consensus"]["GOOG"] = {"verdict": "HOLD"}
    rec = _record(db_path, eng).recording
    goog = [
        get_recommendation(rid, tenant_id=TENANT, db_path=db_path)
        for rid in rec.recommendation_ids
    ]
    goog_row = next(r for r in goog if r and r["symbol"] == "GOOG")

    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        quote = con.execute(
            "SELECT * FROM market_quote_snapshots WHERE id=?",
            (goog_row["market_quote_snapshot_id"],),
        ).fetchone()
    assert quote is not None
    assert quote["quality_state"] == "FRESH"
    assert quote["last"] == pytest.approx(180.5)
