"""Tests for Phase 4B generic recording orchestration (ledger.integration)."""

from __future__ import annotations

import inspect
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from gesh_core.ledger import integration
from gesh_core.ledger.integration import (
    DecisionInput,
    LedgerConflictError,
    LedgerValidationError,
    LedgerWriteError,
    PortfolioInput,
    QuoteInput,
    normalize_timestamp_utc,
    recommendation_id_for,
    record_analysis_decision,
)
from gesh_core.ledger.repository import get_recommendation, insert_recommendation
from gesh_core.ledger.schema import init_ledger_tables

TENANT = "owner"
SOURCE = "daily_analysis_chain"
CTX_A = "ctx_" + "a" * 64
CTX_B = "ctx_" + "b" * 64


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "ledger_integration.db"
    init_ledger_tables(path)
    return path


def _portfolio() -> PortfolioInput:
    return PortfolioInput(
        holdings=[
            {"symbol": "NVDA", "quantity": 10, "avg_cost": 100.0, "current_price": 120.0},
            {"symbol": "AAPL", "quantity": 5, "avg_cost": 150.0, "current_price": 170.0},
        ],
        cash=1000.0,
        buying_power=1000.0,
        total_equity=3050.0,
        captured_at="2026-07-20T09:00:00Z",
    )


def _quotes() -> list[QuoteInput]:
    return [
        QuoteInput(
            symbol="NVDA",
            retrieved_at="2026-07-20T09:00:00Z",
            as_of="2026-07-20T08:59:00Z",
            last=120.0,
        ),
        QuoteInput(symbol="AAPL", retrieved_at="2026-07-20T09:00:00Z", last=170.0),
        QuoteInput(
            symbol="MSFT",
            retrieved_at="2026-07-20T09:00:00Z",
            quality_state="MISSING",
            quality_reason="no_quote_in_payload",
        ),
    ]


def _decisions() -> list[DecisionInput]:
    return [
        DecisionInput(
            symbol="NVDA",
            decision_type="consensus",
            action="BUY",
            conviction=0.8,
            confidence=70.0,
            consensus={"verdict": "BUY", "raw_score": 0.4},
            ai_output={"verdict": "undervalued"},
        ),
        DecisionInput(symbol="AAPL", decision_type="consensus", action="HOLD", confidence=55.0),
        DecisionInput(
            symbol="MSFT",
            decision_type="advisory",
            action="CONSIDER ADDING",
            ai_output={"rationale": "sector balance"},
        ),
    ]


def _record(db_path: Path, **overrides: Any):
    kwargs: dict[str, Any] = {
        "tenant_id": TENANT,
        "source": SOURCE,
        "portfolio": _portfolio(),
        "decisions": _decisions(),
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
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ── happy path / persistence model ──────────────────────────────────────────


def test_happy_path_persists_exact_object_set(db_path: Path):
    rec = _record(db_path)

    assert rec.portfolio_snapshot_id >= 1
    assert rec.portfolio_snapshot_hash.startswith("ps_")
    assert rec.context_hash.startswith("ctx_")
    assert set(rec.market_quote_snapshot_ids) == {"NVDA", "AAPL", "MSFT"}
    assert len(rec.recommendation_ids) == 3
    assert len(rec.inserted_ids) == 3
    assert rec.reused_ids == ()
    for rid in rec.recommendation_ids:
        assert re.fullmatch(r"rec_[0-9a-f]{64}", rid)

    row = get_recommendation(rec.recommendation_ids[0], tenant_id=TENANT, db_path=db_path)
    assert row is not None
    assert row["symbol"] == "NVDA"
    assert row["action"] == "BUY"
    assert row["context_hash"] == rec.context_hash
    assert row["portfolio_snapshot_id"] == rec.portfolio_snapshot_id
    assert row["market_quote_snapshot_id"] == rec.market_quote_snapshot_ids["NVDA"]
    assert row["ai_provider"] == "anthropic"
    assert row["ai_model"] == "claude-sonnet-4-6"
    assert row["analysis_run_id"] == 101
    assert row["source"] == SOURCE
    assert row["decision_at"] == "2026-07-20T09:30:00Z"

    # Persisted: 1 portfolio snapshot, 3 quote snapshots, 3 recommendations.
    assert _count(db_path, "portfolio_snapshots") == 1
    assert _count(db_path, "market_quote_snapshots") == 3
    assert _count(db_path, "recommendations") == 3


def test_missing_price_quote_payload_stored_without_fabrication(db_path: Path):
    rec = _record(db_path)
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM market_quote_snapshots WHERE symbol='MSFT'").fetchone()
    assert row["quality_state"] == "MISSING"
    assert row["quality_reason"] == "no_quote_in_payload"
    assert row["last"] is None and row["bid"] is None and row["ask"] is None
    assert row["volume"] is None and row["as_of"] is None
    assert row["retrieved_at"] is not None  # NOT NULL column always populated

    msft_rec = get_recommendation(rec.recommendation_ids[2], tenant_id=TENANT, db_path=db_path)
    assert msft_rec["market_quote_snapshot_id"] == rec.market_quote_snapshot_ids["MSFT"]


def test_decision_without_quote_links_null_snapshot(db_path: Path):
    decisions = [DecisionInput(symbol="TSLA", decision_type="consensus", action="HOLD")]
    rec = _record(db_path, decisions=decisions, quotes=())
    row = get_recommendation(rec.recommendation_ids[0], tenant_id=TENANT, db_path=db_path)
    assert row["market_quote_snapshot_id"] is None
    assert rec.market_quote_snapshot_ids == {}


def test_decision_types_coexist_for_same_symbol(db_path: Path):
    decisions = [
        DecisionInput(symbol="NVDA", decision_type="consensus", action="BUY"),
        DecisionInput(symbol="NVDA", decision_type="advisory", action="ACCUMULATE"),
    ]
    rec = _record(db_path, decisions=decisions)
    assert len(set(rec.recommendation_ids)) == 2
    assert _count(db_path, "recommendations") == 2


def test_symbols_normalized_to_uppercase(db_path: Path):
    decisions = [DecisionInput(symbol=" brk.b ", decision_type="consensus", action="HOLD")]
    rec = _record(db_path, decisions=decisions, quotes=())
    row = get_recommendation(rec.recommendation_ids[0], tenant_id=TENANT, db_path=db_path)
    assert row["symbol"] == "BRK.B"


# ── idempotent retry / conflict ─────────────────────────────────────────────


def test_full_retry_is_idempotent(db_path: Path):
    first = _record(db_path)
    second = _record(db_path)

    assert second.recommendation_ids == first.recommendation_ids
    assert second.inserted_ids == ()
    assert second.reused_ids == first.recommendation_ids
    assert second.portfolio_snapshot_id == first.portfolio_snapshot_id
    assert second.context_hash == first.context_hash
    assert _count(db_path, "recommendations") == 3
    assert _count(db_path, "portfolio_snapshots") == 1
    assert _count(db_path, "market_quote_snapshots") == 3


def test_partial_recommendation_set_retry_completes(db_path: Path, monkeypatch):
    """Failure after recommendation 3 of 10 leaves a partial set; retry completes it."""
    symbols = [f"SYM{i}" for i in range(10)]
    decisions = [DecisionInput(symbol=s, decision_type="consensus", action="HOLD") for s in symbols]
    quotes = [
        QuoteInput(symbol="SYM0", retrieved_at="2026-07-20T09:00:00Z", last=10.0),
        QuoteInput(symbol="SYM1", retrieved_at="2026-07-20T09:00:00Z", last=20.0),
    ]
    real_insert = integration.insert_recommendation
    calls = {"n": 0}

    def flaky_insert(**kwargs: Any):
        calls["n"] += 1
        if calls["n"] == 4:
            raise sqlite3.OperationalError("simulated mid-chain failure")
        return real_insert(**kwargs)

    monkeypatch.setattr(integration, "insert_recommendation", flaky_insert)
    with pytest.raises(LedgerWriteError):
        _record(db_path, decisions=decisions, quotes=quotes)

    # Partial state: snapshots complete, exactly 3 of 10 recommendations persisted.
    assert _count(db_path, "recommendations") == 3
    assert _count(db_path, "portfolio_snapshots") == 1
    assert _count(db_path, "market_quote_snapshots") == 2

    monkeypatch.setattr(integration, "insert_recommendation", real_insert)
    retry = _record(db_path, decisions=decisions, quotes=quotes)

    assert len(retry.inserted_ids) == 7
    assert len(retry.reused_ids) == 3
    assert len(retry.recommendation_ids) == 10
    assert set(retry.inserted_ids).isdisjoint(retry.reused_ids)
    assert set(retry.inserted_ids) | set(retry.reused_ids) == set(retry.recommendation_ids)
    assert _count(db_path, "recommendations") == 10

    # Third identical call must be pure reuse
    retry3 = _record(db_path, decisions=decisions, quotes=quotes)
    assert len(retry3.inserted_ids) == 0
    assert len(retry3.reused_ids) == 10
    assert set(retry3.recommendation_ids) == set(retry.recommendation_ids)
    assert set(retry3.inserted_ids).isdisjoint(retry3.reused_ids)
    assert _count(db_path, "recommendations") == 10

    # No logical or primary-key duplicates.
    with sqlite3.connect(db_path) as con:
        ids = [r[0] for r in con.execute("SELECT recommendation_id FROM recommendations")]
    assert len(ids) == len(set(ids))

    # All FK references point at this tenant's snapshots from this recording.
    valid_mqs_ids = set(retry.market_quote_snapshot_ids.values())
    for rid in retry.recommendation_ids:
        row = get_recommendation(rid, tenant_id=TENANT, db_path=db_path)
        assert row is not None
        assert row["portfolio_snapshot_id"] == retry.portfolio_snapshot_id
        assert row["market_quote_snapshot_id"] in valid_mqs_ids | {None}


def test_same_id_different_content_raises_conflict(db_path: Path):
    _record(db_path)
    changed = _decisions()
    changed[0] = DecisionInput(
        symbol="NVDA",
        decision_type="consensus",
        action="BUY",
        ai_output={"verdict": "overvalued"},  # same identity (inputs), different content
    )
    with pytest.raises(LedgerConflictError):
        _record(db_path, decisions=changed)


def test_unrelated_integrity_error_becomes_write_error(db_path: Path, monkeypatch):
    """A non-duplicate IntegrityError (FK / CHECK / NOT NULL) maps to LedgerWriteError
    with the sqlite exception preserved in __cause__ — never reuse, never conflict."""

    def fk_violation(**kwargs: Any):
        raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")

    monkeypatch.setattr(integration, "insert_recommendation", fk_violation)
    with pytest.raises(LedgerWriteError) as excinfo:
        _record(db_path)
    assert isinstance(excinfo.value.__cause__, sqlite3.IntegrityError)


def test_duplicate_pk_owned_by_other_tenant_is_write_error(tmp_path: Path):
    """A duplicate PK whose row belongs to another tenant is a write error for this
    tenant — the foreign row is neither reused nor reported as a content conflict."""
    db_a = tmp_path / "a.db"
    init_ledger_tables(db_a)
    learned = _record(db_a)
    rid = learned.recommendation_ids[0]

    db_b = tmp_path / "b.db"
    init_ledger_tables(db_b)
    insert_recommendation(  # foreign-tenant row squatting on the same global PK
        recommendation_id=rid,
        tenant_id="customer-9",
        symbol="NVDA",
        context_hash="ctx_unrelated",
        decision_at="2026-07-20T09:30:00Z",
        source="other_pipeline",
        action="HOLD",
        db_path=db_b,
    )
    with pytest.raises(LedgerWriteError) as excinfo:
        _record(db_b)
    assert isinstance(excinfo.value.__cause__, sqlite3.IntegrityError)
    foreign = get_recommendation(rid, tenant_id="customer-9", db_path=db_b)
    assert foreign is not None and foreign["source"] == "other_pipeline"


def test_analysis_run_id_first_write_wins(db_path: Path):
    """101 -> 102: same identity, idempotent reuse, stored run id stays 101."""
    first = _record(db_path, analysis_run_id=101)
    second = _record(db_path, analysis_run_id=102)

    assert second.recommendation_ids == first.recommendation_ids
    assert second.inserted_ids == ()
    assert len(second.reused_ids) == 3
    assert _count(db_path, "recommendations") == 3
    assert "analysis_run_id" not in integration._FINGERPRINT_COLUMNS
    for rid in first.recommendation_ids:
        row = get_recommendation(rid, tenant_id=TENANT, db_path=db_path)
        assert row is not None
        assert row["analysis_run_id"] == 101  # first write stands; never updated


def test_analysis_run_id_none_to_integer_is_idempotent(db_path: Path):
    before = _count(db_path, "recommendations")
    first = _record(db_path, analysis_run_id=None)
    second = _record(db_path, analysis_run_id=77)
    after = _count(db_path, "recommendations")
    assert second.recommendation_ids == first.recommendation_ids
    assert len(second.reused_ids) == 3
    assert after == before + 3  # no duplicate rows created
    row = get_recommendation(first.recommendation_ids[0], tenant_id=TENANT, db_path=db_path)
    assert row is not None
    assert row["analysis_run_id"] is None  # first write (NULL) stands


def test_analysis_run_id_integer_to_none_is_idempotent(db_path: Path):
    before = _count(db_path, "recommendations")
    first = _record(db_path, analysis_run_id=55)
    second = _record(db_path, analysis_run_id=None)
    after = _count(db_path, "recommendations")
    assert second.recommendation_ids == first.recommendation_ids
    assert len(second.reused_ids) == 3
    assert after == before + 3  # no duplicate rows created
    row = get_recommendation(first.recommendation_ids[0], tenant_id=TENANT, db_path=db_path)
    assert row is not None
    assert row["analysis_run_id"] == 55  # first write stands


def test_analysis_run_id_is_unenforced_metadata(db_path: Path):
    """No FK to analysis_runs: insert succeeds in a DB without that table."""
    rec = _record(db_path, analysis_run_id=999)
    row = get_recommendation(rec.recommendation_ids[0], tenant_id=TENANT, db_path=db_path)
    assert row["analysis_run_id"] == 999
    with sqlite3.connect(db_path) as con:
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "analysis_runs" not in names


# ── recommendation identity ─────────────────────────────────────────────────


def test_equivalent_input_ordering_yields_identical_ids(tmp_path: Path):
    """Holdings/quote ordering is normalized before hashing: equivalent inputs
    in a different order produce identical context hashes and recommendation IDs."""
    db_a = tmp_path / "a.db"
    init_ledger_tables(db_a)
    db_b = tmp_path / "b.db"
    init_ledger_tables(db_b)

    p = _portfolio()
    p_reversed = PortfolioInput(
        holdings=list(reversed(p.holdings)),
        cash=p.cash,
        buying_power=p.buying_power,
        total_equity=p.total_equity,
        captured_at=p.captured_at,
    )
    a = _record(db_a)
    b = _record(db_b, portfolio=p_reversed, quotes=list(reversed(_quotes())))

    assert a.portfolio_snapshot_hash == b.portfolio_snapshot_hash
    assert a.context_hash == b.context_hash
    assert a.recommendation_ids == b.recommendation_ids


def test_prompt_bundle_hash_participates_in_context(db_path: Path):
    """Same prompt_bundle_hash -> identical identity (idempotent reuse). Different
    prompt_bundle_hash -> different context and different, coexisting identities —
    a legitimate new recording, not a conflict."""
    first = _record(db_path, prompt_bundle_hash="pbh_v1")
    retry = _record(db_path, prompt_bundle_hash="pbh_v1")
    assert retry.recommendation_ids == first.recommendation_ids
    assert retry.inserted_ids == ()
    assert len(retry.reused_ids) == 3

    changed = _record(db_path, prompt_bundle_hash="pbh_v2")
    assert changed.context_hash != first.context_hash
    assert set(changed.recommendation_ids).isdisjoint(first.recommendation_ids)
    assert len(changed.inserted_ids) == 3  # new identity -> new rows, no conflict
    assert _count(db_path, "recommendations") == 6


def test_recommendation_id_deterministic_shaped_and_scoped():
    id1 = recommendation_id_for(
        tenant_id=TENANT, symbol="NVDA", decision_type="consensus", context_hash=CTX_A
    )
    id2 = recommendation_id_for(
        tenant_id=TENANT, symbol="NVDA", decision_type="consensus", context_hash=CTX_A
    )
    assert id1 == id2
    assert re.fullmatch(r"rec_[0-9a-f]{64}", id1)

    assert id1 != recommendation_id_for(
        tenant_id="customer-1", symbol="NVDA", decision_type="consensus", context_hash=CTX_A
    )
    assert id1 != recommendation_id_for(
        tenant_id=TENANT, symbol="AAPL", decision_type="consensus", context_hash=CTX_A
    )
    assert id1 != recommendation_id_for(
        tenant_id=TENANT, symbol="NVDA", decision_type="advisory", context_hash=CTX_A
    )
    assert id1 != recommendation_id_for(
        tenant_id=TENANT, symbol="NVDA", decision_type="consensus", context_hash=CTX_B
    )


# ── validation ──────────────────────────────────────────────────────────────


def test_source_and_decision_at_are_required_provenance():
    params = inspect.signature(record_analysis_decision).parameters
    assert params["source"].default is inspect.Parameter.empty
    assert params["decision_at"].default is inspect.Parameter.empty
    # No speculative defaults: provider/model/run-id default to None, never inferred.
    assert params["ai_provider"].default is None
    assert params["ai_model"].default is None
    assert params["analysis_run_id"].default is None


def test_provider_and_model_stay_null_when_not_supplied(db_path: Path):
    rec = _record(db_path, ai_provider=None, ai_model=None)
    row = get_recommendation(rec.recommendation_ids[0], tenant_id=TENANT, db_path=db_path)
    assert row["ai_provider"] is None
    assert row["ai_model"] is None


def test_invalid_inputs_raise_validation_error(db_path: Path):
    with pytest.raises(LedgerValidationError):
        _record(db_path, tenant_id="  ")
    with pytest.raises(LedgerValidationError):
        _record(db_path, source="")
    with pytest.raises(LedgerValidationError):
        _record(db_path, decisions=[])
    with pytest.raises(LedgerValidationError):
        _record(db_path, decision_at="not-a-timestamp")
    with pytest.raises(LedgerValidationError):
        _record(
            db_path,
            decisions=[DecisionInput(symbol="!!", decision_type="consensus", action="HOLD")],
        )
    with pytest.raises(LedgerValidationError):
        _record(
            db_path,
            decisions=[DecisionInput(symbol="NVDA", decision_type="BAD TYPE", action="HOLD")],
        )
    with pytest.raises(LedgerValidationError):
        _record(
            db_path,
            decisions=[DecisionInput(symbol="NVDA", decision_type="consensus", action="  ")],
        )
    with pytest.raises(LedgerValidationError):
        _record(
            db_path,
            decisions=[
                DecisionInput(
                    symbol="NVDA", decision_type="consensus", action="HOLD", conviction=float("nan")
                )
            ],
        )
    with pytest.raises(LedgerValidationError):
        _record(
            db_path,
            quotes=[
                QuoteInput(
                    symbol="NVDA", retrieved_at="2026-07-20T09:00:00Z", quality_state="BOGUS"
                )
            ],
        )


def test_duplicate_quote_symbol_rejected(db_path: Path):
    quotes = [
        QuoteInput(symbol="NVDA", retrieved_at="2026-07-20T09:00:00Z", last=1.0),
        QuoteInput(symbol="nvda", retrieved_at="2026-07-20T09:00:00Z", last=2.0),
    ]
    with pytest.raises(LedgerValidationError):
        _record(db_path, quotes=quotes)


def test_non_finite_portfolio_floats_rejected(db_path: Path):
    p = PortfolioInput(
        holdings=[],
        cash=float("inf"),
        buying_power=None,
        total_equity=None,
        captured_at="2026-07-20T09:00:00Z",
    )
    with pytest.raises(LedgerValidationError):
        _record(db_path, portfolio=p)


# ── timestamps ──────────────────────────────────────────────────────────────


def test_normalize_timestamp_utc():
    assert normalize_timestamp_utc("2026-07-20T09:30:00+00:00", field="t") == "2026-07-20T09:30:00Z"
    assert normalize_timestamp_utc("2026-07-20T09:30:00Z", field="t") == "2026-07-20T09:30:00Z"
    assert normalize_timestamp_utc("2026-07-20T11:30:00+02:00", field="t") == "2026-07-20T09:30:00Z"
    assert (
        normalize_timestamp_utc(datetime(2026, 7, 20, 9, 30), field="t") == "2026-07-20T09:30:00Z"
    )
    aware = datetime(2026, 7, 20, 9, 30, tzinfo=UTC)
    assert normalize_timestamp_utc(aware, field="t") == "2026-07-20T09:30:00Z"
    with pytest.raises(LedgerValidationError):
        normalize_timestamp_utc("", field="t")
    with pytest.raises(LedgerValidationError):
        normalize_timestamp_utc("yesterday", field="t")
    with pytest.raises(LedgerValidationError):
        normalize_timestamp_utc(None, field="t")  # type: ignore[arg-type]
