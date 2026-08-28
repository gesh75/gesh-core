"""Adapter quote integrity: never persist a zero/negative/non-finite price as FRESH.

The daily-analysis adapter hashes quote snapshots into the ledger. Fabricating
``FRESH`` at $0 (or keeping NaN/Inf) would poison valuation context for every
downstream recommendation that links that snapshot.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from gesh_core.ledger.adapters.daily_analysis import record_daily_analysis_decision
from gesh_core.ledger.schema import init_ledger_tables

TENANT = "owner"
SOURCE = "daily_analysis_chain"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "ledger_quote_integrity.db"
    init_ledger_tables(path)
    return path


def _eng(*, symbol: str = "NVDA", **holding_overrides: Any) -> dict[str, Any]:
    holding: dict[str, Any] = {
        "symbol": symbol,
        "quantity": 10,
        "average_buy_price": 100.0,
        "current_price": 120.0,
        "equity": 1200.0,
    }
    holding.update(holding_overrides)
    return {
        "holdings": [holding],
        "equity_summary": {"cash": 1000.0, "total": 2200.0},
        "consensus": {symbol: {"verdict": "HOLD", "confidence": 50.0}},
        "ai_result": {"holdings_analysis": [], "portfolio_recommendations": []},
        "ai_result_ran_at": "2026-07-20T09:30:00+00:00",
        "run_manifest": {
            "snapshot_as_of": "2026-07-20T09:00:00Z",
            "quote_as_of": {symbol: "2026-07-20T08:59:00Z"},
        },
        "snapshot": {"fetched_at": "2026-07-20T09:00:00Z"},
    }


def _record(db_path: Path, eng: dict[str, Any]) -> Any:
    return record_daily_analysis_decision(
        tenant_id=TENANT,
        source=SOURCE,
        engine_results=eng,
        analysis_run_id=101,
        ai_provider="anthropic",
        ai_model="claude-sonnet-4-6",
        db_path=db_path,
    )


def _mqs(db_path: Path, symbol: str) -> dict[str, Any]:
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM market_quote_snapshots WHERE symbol=? ORDER BY id DESC LIMIT 1",
            (symbol,),
        ).fetchone()
    assert row is not None
    return dict(row)


@pytest.mark.parametrize(
    "holding_overrides",
    [
        {"current_price": 0},
        {"current_price": -1.5},
        {"current_price": "nan"},
        {"current_price": float("inf")},
        {"current_price": float("-inf")},
        {"current_price": "not-a-price"},
    ],
)
def test_non_positive_or_junk_held_price_is_missing_not_fresh(
    db_path: Path, holding_overrides: dict[str, Any]
) -> None:
    _record(db_path, _eng(**holding_overrides))
    row = _mqs(db_path, "NVDA")
    assert row["quality_state"] == "MISSING"
    assert row["last"] is None
    assert row["quality_reason"] == "no_quote_in_payload"


def test_positive_held_price_stays_fresh(db_path: Path) -> None:
    _record(db_path, _eng(current_price=142.25))
    row = _mqs(db_path, "NVDA")
    assert row["quality_state"] == "FRESH"
    assert row["last"] == pytest.approx(142.25)


def test_price_alias_used_when_current_price_absent(db_path: Path) -> None:
    eng = _eng()
    del eng["holdings"][0]["current_price"]
    eng["holdings"][0]["price"] = 88.5
    _record(db_path, eng)
    row = _mqs(db_path, "NVDA")
    assert row["quality_state"] == "FRESH"
    assert row["last"] == pytest.approx(88.5)


def test_explicit_zero_current_price_wins_over_price_alias(db_path: Path) -> None:
    """``dict.get`` prefers a present zero over the ``price`` alias — do not fabricate."""
    _record(db_path, _eng(current_price=0, price=88.5))
    row = _mqs(db_path, "NVDA")
    assert row["quality_state"] == "MISSING"
    assert row["last"] is None


def test_unheld_advisory_symbol_is_missing(db_path: Path) -> None:
    eng = _eng()
    eng["ai_result"]["portfolio_recommendations"] = [
        {
            "action": "Consider adding",
            "category": "DIVERSIFICATION",
            "symbol": "MSFT",
            "rationale": "sector balance",
        }
    ]
    _record(db_path, eng)
    row = _mqs(db_path, "MSFT")
    assert row["quality_state"] == "MISSING"
    assert row["last"] is None
