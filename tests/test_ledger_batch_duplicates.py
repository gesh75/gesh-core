"""Intra-recording duplicate decisions must fail closed before a second insert.

recommendation_id is deterministic on (tenant, symbol, decision_type, context,
decision_at). Two identical (symbol, type) rows in one batch would collide on
that id; the orchestrator must raise LedgerValidationError rather than treating
the second as a conflict or silently skipping it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from gesh_core.ledger.integration import (
    DecisionInput,
    LedgerValidationError,
    PortfolioInput,
    QuoteInput,
    record_analysis_decision,
)
from gesh_core.ledger.schema import init_ledger_tables

TENANT = "owner"
SOURCE = "daily_analysis_chain"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "ledger_batch_dup.db"
    init_ledger_tables(path)
    return path


def _portfolio() -> PortfolioInput:
    return PortfolioInput(
        holdings=[{"symbol": "NVDA", "quantity": 10, "avg_cost": 100.0, "current_price": 120.0}],
        cash=1000.0,
        buying_power=1000.0,
        total_equity=2200.0,
        captured_at="2026-07-20T09:00:00Z",
    )


def _quotes() -> list[QuoteInput]:
    return [QuoteInput(symbol="NVDA", retrieved_at="2026-07-20T09:00:00Z", last=120.0)]


def _record(db_path: Path, decisions: list[DecisionInput], **overrides: Any) -> Any:
    kwargs: dict[str, Any] = {
        "tenant_id": TENANT,
        "source": SOURCE,
        "portfolio": _portfolio(),
        "decisions": decisions,
        "decision_at": "2026-07-20T09:30:00Z",
        "quotes": _quotes(),
        "ai_provider": "anthropic",
        "ai_model": "claude-sonnet-4-6",
        "analysis_run_id": 101,
        "db_path": db_path,
    }
    kwargs.update(overrides)
    return record_analysis_decision(**kwargs)


def _count(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as con:
        return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_duplicate_symbol_and_type_in_one_batch_is_validation_error(db_path: Path) -> None:
    decisions = [
        DecisionInput(symbol="NVDA", decision_type="consensus", action="BUY", confidence=70.0),
        DecisionInput(symbol="NVDA", decision_type="consensus", action="HOLD", confidence=40.0),
    ]
    with pytest.raises(LedgerValidationError, match=r"duplicate decision NVDA/consensus"):
        _record(db_path, decisions)
    # First row is inserted, then the second collides — never two rows.
    assert _count(db_path, "recommendations") == 1


def test_same_symbol_different_types_are_not_duplicates(db_path: Path) -> None:
    decisions = [
        DecisionInput(symbol="NVDA", decision_type="consensus", action="BUY", confidence=70.0),
        DecisionInput(
            symbol="NVDA",
            decision_type="advisory",
            action="CONSIDER ADDING",
            ai_output={"rationale": "sector"},
        ),
    ]
    rec = _record(db_path, decisions)
    assert len(rec.recommendation_ids) == 2
    assert len(set(rec.recommendation_ids)) == 2
    assert _count(db_path, "recommendations") == 2


def test_casefolded_symbol_duplicate_is_still_rejected(db_path: Path) -> None:
    decisions = [
        DecisionInput(symbol="nvda", decision_type="consensus", action="BUY"),
        DecisionInput(symbol="NVDA", decision_type="consensus", action="HOLD"),
    ]
    with pytest.raises(LedgerValidationError, match="duplicate decision"):
        _record(db_path, decisions)
