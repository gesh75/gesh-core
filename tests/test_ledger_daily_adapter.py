"""Tests for the owner daily-analysis-chain adapter (ledger.adapters.daily_analysis)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from gesh_core.ledger.adapters.daily_analysis import (
    SkippedDecision,
    record_daily_analysis_decision,
)
from gesh_core.ledger.hashes import portfolio_snapshot_hash
from gesh_core.ledger.integration import LedgerValidationError
from gesh_core.ledger.repository import get_portfolio_snapshot, get_recommendation
from gesh_core.ledger.schema import init_ledger_tables

TENANT = "owner"
SOURCE = "daily_analysis_chain"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "ledger_adapter.db"
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
                "equity": 1200.0,
                "token": "must-not-be-stored",
                "unrelated_field": 42,
            },
            {
                "symbol": "AAPL",
                "quantity": 5,
                "average_buy_price": 150.0,
                "current_price": 170.0,
                "equity": 850.0,
            },
        ],
        "equity_summary": {"cash": 1000.0, "total": 3050.0},
        "consensus": {
            "NVDA": {
                "verdict": "BUY",
                "conviction": 0.6,
                "confidence": 70.0,
                "raw_score": 0.4,
                "tilt": "bullish",
                "regime": "TRENDING",
                "as_of": "2026-07-20T09:00:00Z",
                "votes": {"momentum": 1},
                "details": {"momentum": "rsi fine"},
            },
            "AAPL": {"verdict": "HOLD", "confidence": 55.0},
        },
        "ai_result": {
            "holdings_analysis": [
                {
                    "symbol": "NVDA",
                    "verdict": "undervalued",
                    "fair_value": {
                        "estimate": 150.0,
                        "current": 120.0,
                        "status": "undervalued",
                        "pct_diff": 25.0,
                    },
                    "scores": {"valuation": 70},
                    "analyst_note": "long prose",
                    "api_key": "must-not-be-stored",
                },
                {"symbol": "AAPL", "verdict": "fairly valued"},
            ],
            "portfolio_recommendations": [
                {
                    "action": "Consider adding",
                    "priority": "medium",
                    "rationale": "sector balance",
                    "category": "DIVERSIFICATION",
                    "symbol": "MSFT",
                },
                {"action": "Trim winners", "priority": "low", "rationale": "rebalance prose"},
            ],
        },
        "ai_result_ran_at": "2026-07-20T09:30:00+00:00",
        "run_manifest": {
            "snapshot_as_of": "2026-07-20T09:00:00Z",
            "quote_as_of": {"NVDA": "2026-07-20T08:59:00Z", "AAPL": "2026-07-20T08:59:00Z"},
        },
        "snapshot": {"fetched_at": "2026-07-20T09:00:00Z"},
    }


def _record(db_path: Path, eng: dict[str, Any] | None = None, **overrides: Any):
    kwargs: dict[str, Any] = {
        "tenant_id": TENANT,
        "source": SOURCE,
        "engine_results": eng if eng is not None else _eng(),
        "analysis_run_id": 101,
        "ai_provider": "anthropic",
        "ai_model": "claude-sonnet-4-6",
        "db_path": db_path,
    }
    kwargs.update(overrides)
    return record_daily_analysis_decision(**kwargs)


def _rec_row(db_path: Path, rid: str) -> dict[str, Any]:
    row = get_recommendation(rid, tenant_id=TENANT, db_path=db_path)
    assert row is not None
    return row


def _mqs_row(db_path: Path, symbol: str) -> dict[str, Any]:
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM market_quote_snapshots WHERE symbol=? ORDER BY id DESC LIMIT 1",
            (symbol,),
        ).fetchone()
    assert row is not None
    return dict(row)


# ── happy path ──────────────────────────────────────────────────────────────


def test_adapter_happy_path(db_path: Path):
    result = _record(db_path)
    rec = result.recording

    # Universe: NVDA + AAPL (consensus) and MSFT (advisory). Prose item without
    # category is not recorded.
    assert len(rec.recommendation_ids) == 3
    assert result.skipped == ()

    # Consensus decisions are recorded in sorted symbol order: AAPL, NVDA.
    nvda = _rec_row(db_path, rec.recommendation_ids[1])
    assert nvda["symbol"] == "NVDA"
    assert nvda["action"] == "BUY"  # consensus verdict -> action
    assert nvda["conviction"] == 0.6
    assert nvda["confidence"] == 70.0
    assert nvda["source"] == SOURCE
    assert nvda["ai_provider"] == "anthropic"
    assert nvda["ai_model"] == "claude-sonnet-4-6"
    assert nvda["analysis_run_id"] == 101
    assert nvda["decision_at"] == "2026-07-20T09:30:00Z"

    consensus_json = json.loads(nvda["consensus_json"])
    assert consensus_json["verdict"] == "BUY"
    assert consensus_json["raw_score"] == 0.4
    assert "votes" not in consensus_json and "details" not in consensus_json

    ai_output = json.loads(nvda["ai_output_json"])
    assert ai_output["verdict"] == "undervalued"
    assert ai_output["fair_value"]["estimate"] == 150.0
    assert "analyst_note" not in ai_output and "api_key" not in ai_output

    msft = _rec_row(db_path, rec.recommendation_ids[2])
    assert msft["action"] == "CONSIDER ADDING"  # uppercased advisory action

    # Quotes: held symbols FRESH with real prices, advisory-only symbol MISSING.
    assert _mqs_row(db_path, "NVDA")["last"] == 120.0
    assert _mqs_row(db_path, "NVDA")["quality_state"] == "FRESH"
    assert _mqs_row(db_path, "NVDA")["as_of"] == "2026-07-20T08:59:00Z"
    assert _mqs_row(db_path, "AAPL")["last"] == 170.0
    msft_mqs = _mqs_row(db_path, "MSFT")
    assert msft_mqs["quality_state"] == "MISSING"
    assert msft_mqs["last"] is None
    assert msft_mqs["retrieved_at"] == "2026-07-20T09:00:00Z"
    assert msft["market_quote_snapshot_id"] == rec.market_quote_snapshot_ids["MSFT"]


def test_adapter_maps_average_buy_price_to_avg_cost(db_path: Path):
    result = _record(db_path)
    rec = result.recording

    ps = get_portfolio_snapshot(rec.portfolio_snapshot_id, tenant_id=TENANT, db_path=db_path)
    assert ps is not None
    holdings = json.loads(ps["holdings_json"])
    assert len(holdings) == 2
    for row in holdings:
        assert set(row) == {"symbol", "quantity", "avg_cost", "current_price"}
        assert "average_buy_price" not in row
    by_symbol = {h["symbol"]: h for h in holdings}
    assert by_symbol["NVDA"]["avg_cost"] == 100.0
    assert by_symbol["AAPL"]["avg_cost"] == 150.0

    # The snapshot hash matches the canonical hash over the NORMALIZED rows.
    expected = portfolio_snapshot_hash(
        tenant_id=TENANT,
        holdings=[
            {"symbol": "NVDA", "quantity": 10, "avg_cost": 100.0, "current_price": 120.0},
            {"symbol": "AAPL", "quantity": 5, "avg_cost": 150.0, "current_price": 170.0},
        ],
        cash=1000.0,
        buying_power=None,
        total_equity=3050.0,
    )
    assert rec.portfolio_snapshot_hash == expected
    assert ps["captured_at"] == "2026-07-20T09:00:00Z"


def test_adapter_secret_fields_never_stored_and_hashes_unaffected(db_path: Path):
    """Raw payloads carry token/api_key: recording succeeds, nothing leaks, and
    unrelated legacy fields do not enter any hash or stored JSON."""
    first = _record(db_path)

    ps = get_portfolio_snapshot(
        first.recording.portfolio_snapshot_id, tenant_id=TENANT, db_path=db_path
    )
    stored_holdings = ps["holdings_json"]
    assert "token" not in stored_holdings
    assert "unrelated_field" not in stored_holdings

    nvda = _rec_row(db_path, first.recording.recommendation_ids[0])
    assert "api_key" not in (nvda["ai_output_json"] or "")

    # Mutating an unrelated legacy field must not change identity or content.
    eng2 = _eng()
    eng2["holdings"][0]["unrelated_field"] = 999999
    eng2["holdings"][0]["another_new_junk_key"] = {"nested": "junk"}
    second = _record(db_path, eng=eng2)
    assert second.recording.recommendation_ids == first.recording.recommendation_ids
    assert second.recording.inserted_ids == ()
    assert len(second.recording.reused_ids) == 3


def test_adapter_idempotent_retry(db_path: Path):
    first = _record(db_path)
    second = _record(db_path)
    assert second.recording.recommendation_ids == first.recording.recommendation_ids
    assert second.recording.inserted_ids == ()
    assert len(second.recording.reused_ids) == 3
    assert second.skipped == first.skipped


# ── symbol universe rules ───────────────────────────────────────────────────


def test_adapter_symbol_rules(db_path: Path):
    eng = _eng()
    eng["holdings"].append(
        {"symbol": "TSLA", "quantity": 1, "average_buy_price": 200.0, "current_price": 210.0}
    )  # holding with quote but no consensus entry
    eng["holdings"].append(
        {"symbol": "CASH", "quantity": 100, "average_buy_price": 1.0, "current_price": 1.0}
    )  # cash-like pseudo-position
    eng["holdings"].append(
        {"symbol": "IBM", "quantity": 2, "average_buy_price": 180.0, "current_price": 190.0}
    )  # held AND has a blank-verdict consensus entry (double-report guard)
    eng["consensus"]["GOOG"] = {"verdict": "SELL", "confidence": 40.0}  # not in holdings
    eng["consensus"]["bad!!sym"] = {"verdict": "HOLD"}  # malformed
    eng["consensus"]["CUR:USD"] = {"verdict": "HOLD"}  # cash-like
    eng["consensus"]["IBM"] = {"verdict": ""}  # blank verdict
    eng["ai_result"]["portfolio_recommendations"] += [
        {
            "action": "Add more MSFT",
            "priority": "low",
            "rationale": "dup",
            "category": "DIVERSIFICATION",
            "symbol": "MSFT",
        },
        {
            "action": "Buy the dollar",
            "priority": "low",
            "rationale": "fx",
            "category": "DIVERSIFICATION",
            "symbol": "CUR:USD",
        },
        {
            "action": "Mystery idea",
            "priority": "low",
            "rationale": "no symbol",
            "category": "DIVERSIFICATION",
        },
        {
            "action": "   ",
            "priority": "low",
            "rationale": "no action",
            "category": "DIVERSIFICATION",
            "symbol": "AMD",
        },
    ]

    result = _record(db_path, eng=eng)
    rec = result.recording

    # Recorded: NVDA, AAPL (consensus), GOOG (consensus, not held), MSFT (advisory).
    # Consensus rows come first in sorted symbol order: AAPL, GOOG, NVDA.
    assert len(rec.recommendation_ids) == 4
    goog = _rec_row(db_path, rec.recommendation_ids[1])
    assert goog["symbol"] == "GOOG"
    assert goog["action"] == "SELL"
    assert _mqs_row(db_path, "GOOG")["quality_state"] == "MISSING"  # no quote in payload

    reasons = {(s.symbol, s.reason) for s in result.skipped}
    assert ("TSLA", "no_consensus_verdict") in reasons
    assert ("IBM", "no_consensus_verdict") in reasons
    assert ("BAD!!SYM", "invalid_symbol") in reasons
    assert ("CUR:USD", "cash_like_symbol") in reasons
    assert ("MSFT", "duplicate_symbol") in reasons
    assert (None, "missing_symbol") in reasons
    assert ("AMD", "missing_action") in reasons
    # Cash-like holding produces no recommendation and no skipped entry.
    assert not any(s.symbol == "CASH" for s in result.skipped)

    # Blank-verdict holding: exactly ONE skipped entry with the exact reason, and
    # no duplicate (symbol, decision_type, reason) tuples anywhere in skipped.
    ibm = [s for s in result.skipped if s.symbol == "IBM"]
    assert ibm == [
        SkippedDecision(symbol="IBM", decision_type="consensus", reason="no_consensus_verdict")
    ]
    tuples = [(s.symbol, s.decision_type, s.reason) for s in result.skipped]
    assert len(tuples) == len(set(tuples))

    # TSLA's and IBM's positions are still fully preserved in the portfolio snapshot.
    ps = get_portfolio_snapshot(rec.portfolio_snapshot_id, tenant_id=TENANT, db_path=db_path)
    held = {h["symbol"] for h in json.loads(ps["holdings_json"])}
    assert "TSLA" in held
    assert "IBM" in held


def test_adapter_empty_universe_raises(db_path: Path):
    eng = _eng()
    eng["consensus"] = {}
    eng["ai_result"]["portfolio_recommendations"] = []
    with pytest.raises(LedgerValidationError):
        _record(db_path, eng=eng)


# ── timestamp precedence ────────────────────────────────────────────────────


def test_adapter_decision_at_precedence(db_path: Path):
    # Explicit override wins over ai_result_ran_at.
    result = _record(db_path, decision_at="2026-07-20T10:05:00Z")
    row = _rec_row(db_path, result.recording.recommendation_ids[0])
    assert row["decision_at"] == "2026-07-20T10:05:00Z"


def test_adapter_decision_at_from_ai_result_ran_at(db_path: Path):
    result = _record(db_path)
    row = _rec_row(db_path, result.recording.recommendation_ids[0])
    assert row["decision_at"] == "2026-07-20T09:30:00Z"  # +00:00 normalized to Z


def test_adapter_missing_decision_time_raises(db_path: Path):
    eng = _eng()
    del eng["ai_result_ran_at"]
    with pytest.raises(LedgerValidationError):
        _record(db_path, eng=eng)


def test_adapter_invalid_decision_time_raises(db_path: Path):
    eng = _eng()
    eng["ai_result_ran_at"] = "not-a-time"
    with pytest.raises(LedgerValidationError):
        _record(db_path, eng=eng)


def test_adapter_fetched_at_falls_back_to_manifest(db_path: Path):
    eng = _eng()
    eng["snapshot"] = {}  # no fetched_at -> run_manifest.snapshot_as_of
    result = _record(db_path, eng=eng)
    ps = get_portfolio_snapshot(
        result.recording.portfolio_snapshot_id, tenant_id=TENANT, db_path=db_path
    )
    assert ps["captured_at"] == "2026-07-20T09:00:00Z"


def test_adapter_missing_portfolio_time_raises(db_path: Path):
    eng = _eng()
    eng["snapshot"] = {}
    eng["run_manifest"] = {}
    with pytest.raises(LedgerValidationError):
        _record(db_path, eng=eng)


# ── explicit provenance ─────────────────────────────────────────────────────


def test_adapter_provider_and_model_explicit(db_path: Path):
    result = _record(db_path, ai_provider=None, ai_model=None)
    row = _rec_row(db_path, result.recording.recommendation_ids[0])
    assert row["ai_provider"] is None
    assert row["ai_model"] is None


def test_skipped_decision_shape(db_path: Path):
    eng = _eng()
    eng["consensus"]["bad!!sym"] = {"verdict": "HOLD"}
    result = _record(db_path, eng=eng)
    assert (
        SkippedDecision(symbol="BAD!!SYM", decision_type="consensus", reason="invalid_symbol")
        in result.skipped
    )
