"""Recommendation identity v2: normalized decision_at participates in the ID.

Root cause of the v0.6.0 production failure (LedgerConflictError on the first
owner smoke): identity omitted ``decision_at`` while the stored-content
fingerprint (``_FINGERPRINT_COLUMNS``) includes it. Two AI executions over an
identical decision-input context therefore computed the SAME recommendation_id
but stored DIFFERENT content, and the conflict guard fired.

context_hash intentionally identifies the decision *input context*, not one
execution run, so the execution timestamp — not the context — is what must
separate two runs. analysis_run_id stays provenance-only and out of identity.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from gesh_core.ledger.integration import (
    DecisionInput,
    LedgerConflictError,
    PortfolioInput,
    QuoteInput,
    recommendation_id_for,
    record_analysis_decision,
)
from gesh_core.ledger.repository import get_recommendation, insert_recommendation
from gesh_core.ledger.schema import init_ledger_tables

TENANT = "owner"
SOURCE = "daily_analysis_chain"
CTX_A = "ctx_" + "a" * 64
CTX_B = "ctx_" + "b" * 64
T1 = "2026-07-24T17:05:00Z"
T2 = "2026-07-24T21:55:00Z"  # a later execution over the SAME context


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "ledger_identity_v2.db"
    init_ledger_tables(path)
    return path


def _portfolio() -> PortfolioInput:
    return PortfolioInput(
        holdings=[{"symbol": "NVDA", "quantity": 10, "avg_cost": 100.0}],
        cash=1000.0,
        buying_power=1000.0,
        total_equity=2200.0,
        captured_at="2026-07-24T17:00:00Z",
    )


def _quotes() -> list[QuoteInput]:
    return [QuoteInput(symbol="NVDA", retrieved_at="2026-07-24T17:00:00Z", last=120.0)]


def _decisions(*, action: str = "BUY", confidence: float = 70.0) -> list[DecisionInput]:
    """One decision; action/confidence vary to model probabilistic reruns."""
    return [
        DecisionInput(
            symbol="NVDA",
            decision_type="consensus",
            action=action,
            confidence=confidence,
        )
    ]


def _record(db_path: Path, **overrides: Any):
    kwargs: dict[str, Any] = {
        "tenant_id": TENANT,
        "source": SOURCE,
        "portfolio": _portfolio(),
        "decisions": _decisions(),
        "decision_at": T1,
        "quotes": _quotes(),
        "ai_provider": "anthropic",
        "ai_model": "claude-sonnet-4-6",
        "analysis_run_id": 178,
        "db_path": db_path,
    }
    kwargs.update(overrides)
    return record_analysis_decision(**kwargs)


def _count(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as con:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ── root cause ───────────────────────────────────────────────────────────────


def test_root_cause_second_execution_same_context_does_not_conflict(db_path: Path):
    """THE v0.6.0 REGRESSION.

    Identical portfolio / quotes / provider / model / prompt context and
    identical decision content, differing ONLY in decision_at. Under v1 this
    raised LedgerConflictError; under v2 it is a distinct, coexisting identity.
    """
    first = _record(db_path, decision_at=T1)
    assert len(first.inserted_ids) == 1

    second = _record(db_path, decision_at=T2)  # v1: LedgerConflictError

    assert second.context_hash == first.context_hash, "context must be unchanged"
    assert set(second.recommendation_ids).isdisjoint(first.recommendation_ids)
    assert len(second.inserted_ids) == 1
    assert second.reused_ids == ()
    assert _count(db_path, "recommendations") == 2


def test_root_cause_is_not_an_intra_recording_duplicate(db_path: Path):
    """Distinguishes the defect from a same-call duplicate (LedgerValidationError)."""
    first = _record(db_path, decision_at=T1)
    second = _record(db_path, decision_at=T2)
    for rec in (first, second):
        assert len(rec.recommendation_ids) == len(set(rec.recommendation_ids))


# ── A–I semantic contract ────────────────────────────────────────────────────


def test_A_exact_retry_is_idempotent(db_path: Path):
    first = _record(db_path, decision_at=T1)
    retry = _record(db_path, decision_at=T1)
    assert retry.recommendation_ids == first.recommendation_ids
    assert retry.inserted_ids == ()
    assert len(retry.reused_ids) == 1
    assert _count(db_path, "recommendations") == 1


def test_B_new_execution_identical_content_persists_both(db_path: Path):
    first = _record(db_path, decision_at=T1)
    second = _record(db_path, decision_at=T2)
    assert set(second.recommendation_ids).isdisjoint(first.recommendation_ids)
    for rid in list(first.recommendation_ids) + list(second.recommendation_ids):
        assert get_recommendation(rid, tenant_id=TENANT, db_path=db_path) is not None
    assert _count(db_path, "recommendations") == 2


def test_C_probabilistic_rerun_different_output_no_conflict(db_path: Path):
    first = _record(db_path, decision_at=T1, decisions=_decisions(action="BUY", confidence=70.0))
    second = _record(db_path, decision_at=T2, decisions=_decisions(action="HOLD", confidence=44.0))
    assert set(second.recommendation_ids).isdisjoint(first.recommendation_ids)
    assert len(second.inserted_ids) == 1
    assert _count(db_path, "recommendations") == 2


def test_D_same_execution_different_content_still_conflicts(db_path: Path):
    """Conflict detection must NOT be weakened: same identity + changed content raises."""
    _record(db_path, decision_at=T1, decisions=_decisions(action="BUY", confidence=70.0))
    with pytest.raises(LedgerConflictError):
        _record(db_path, decision_at=T1, decisions=_decisions(action="SELL", confidence=70.0))


def test_E_analysis_run_id_only_difference_is_reuse(db_path: Path):
    """analysis_run_id is provenance, never identity."""
    first = _record(db_path, decision_at=T1, analysis_run_id=178)
    again = _record(db_path, decision_at=T1, analysis_run_id=179)
    assert again.recommendation_ids == first.recommendation_ids
    assert again.inserted_ids == ()
    assert len(again.reused_ids) == 1
    assert _count(db_path, "recommendations") == 1


def test_F_partial_write_retry_completes_the_set(db_path: Path):
    """A pre-seeded identical row is reused; the rest of the set inserts."""
    two = [
        DecisionInput(symbol="NVDA", decision_type="consensus", action="BUY", confidence=70.0),
        DecisionInput(symbol="AAPL", decision_type="consensus", action="HOLD", confidence=55.0),
    ]
    first = _record(db_path, decision_at=T1, decisions=two)
    assert len(first.inserted_ids) == 2

    retry = _record(db_path, decision_at=T1, decisions=two)
    assert retry.inserted_ids == ()
    assert len(retry.reused_ids) == 2
    assert _count(db_path, "recommendations") == 2


def test_G_v1_row_coexists_with_v2_identity(db_path: Path):
    """A legacy v1-shaped row (ID computed without decision_at) stays readable
    and does not collide with the v2 identity for the same context."""
    rec = _record(db_path, decision_at=T1)
    v2_id = rec.recommendation_ids[0]
    row = get_recommendation(v2_id, tenant_id=TENANT, db_path=db_path)
    assert row is not None

    # Legacy v1 identity payload: tenant/symbol/decision_type/context_hash only.
    from gesh_core.ledger.canonical import content_hash

    v1_id = content_hash(
        {
            "schema_version": 1,
            "tenant_id": TENANT,
            "symbol": "NVDA",
            "decision_type": "consensus",
            "context_hash": row["context_hash"],
        },
        prefix="rec",
    )
    assert v1_id != v2_id

    insert_recommendation(
        recommendation_id=v1_id,
        tenant_id=TENANT,
        symbol="NVDA",
        context_hash=row["context_hash"],
        decision_at=T1,
        source=SOURCE,
        action="BUY",
        analysis_run_id=178,
        portfolio_snapshot_id=row["portfolio_snapshot_id"],
        market_quote_snapshot_id=row["market_quote_snapshot_id"],
        db_path=db_path,
    )

    assert get_recommendation(v1_id, tenant_id=TENANT, db_path=db_path) is not None
    assert get_recommendation(v2_id, tenant_id=TENANT, db_path=db_path) is not None
    assert _count(db_path, "recommendations") == 2


def test_H_id_format_unchanged(db_path: Path):
    rid = recommendation_id_for(
        tenant_id=TENANT,
        symbol="NVDA",
        decision_type="consensus",
        context_hash=CTX_A,
        decision_at=T1,
    )
    assert re.fullmatch(r"rec_[0-9a-f]{64}", rid)


def test_I_identity_sensitivity_all_fields(db_path: Path):
    base = dict(
        tenant_id=TENANT,
        symbol="NVDA",
        decision_type="consensus",
        context_hash=CTX_A,
        decision_at=T1,
    )
    rid = recommendation_id_for(**base)
    assert rid == recommendation_id_for(**base)  # deterministic

    assert rid != recommendation_id_for(**{**base, "tenant_id": "customer-1"})
    assert rid != recommendation_id_for(**{**base, "symbol": "AAPL"})
    assert rid != recommendation_id_for(**{**base, "decision_type": "advisory"})
    assert rid != recommendation_id_for(**{**base, "context_hash": CTX_B})
    assert rid != recommendation_id_for(**{**base, "decision_at": T2})


def test_decision_at_is_normalized_before_hashing():
    """Equivalent instants in different notations yield the same identity."""
    a = recommendation_id_for(
        tenant_id=TENANT,
        symbol="NVDA",
        decision_type="consensus",
        context_hash=CTX_A,
        decision_at="2026-07-24T17:05:00Z",
    )
    b = recommendation_id_for(
        tenant_id=TENANT,
        symbol="NVDA",
        decision_type="consensus",
        context_hash=CTX_A,
        decision_at="2026-07-24T20:05:00+03:00",
    )
    assert a == b


def _id_at(decision_at: datetime | str) -> str:
    """Identity for a fixed context, varying only decision_at."""
    return recommendation_id_for(
        tenant_id=TENANT,
        symbol="NVDA",
        decision_type="consensus",
        context_hash=CTX_A,
        decision_at=decision_at,
    )


def test_timezone_equivalence_all_notations_one_identity():
    """One instant written five ways must produce exactly one identity.

    Covers Z, explicit +00:00, an equivalent NEGATIVE UTC offset, a naive
    string, and an aware datetime object. Naive input is interpreted as UTC —
    the documented rule of ``normalize_timestamp_utc`` — so the naive form of
    an already-UTC wall time is the same instant, not a shifted one.
    """
    ids = {
        "Z": _id_at("2026-07-24T17:05:00Z"),
        "+00:00": _id_at("2026-07-24T17:05:00+00:00"),
        # 12:05 at UTC-05:00 is the same instant as 17:05 UTC.
        "-05:00": _id_at("2026-07-24T12:05:00-05:00"),
        # Naive == UTC per the documented rule.
        "naive": _id_at("2026-07-24T17:05:00"),
        "datetime": _id_at(datetime(2026, 7, 24, 17, 5, 0, tzinfo=UTC)),
    }
    assert len(set(ids.values())) == 1, f"notations diverged: {ids}"


def test_naive_is_utc_not_local_time():
    """Guards the documented rule itself: naive is UTC, never local."""
    # A naive 17:05 must equal 17:05Z, and must NOT equal a different instant.
    assert _id_at("2026-07-24T17:05:00") == _id_at("2026-07-24T17:05:00Z")
    assert _id_at("2026-07-24T17:05:00") != _id_at("2026-07-24T12:05:00Z")


def test_one_microsecond_changes_identity():
    """Sub-second resolution is preserved: 1 µs apart is a distinct execution."""
    base = "2026-07-24T18:55:07.627670Z"
    plus_1us = "2026-07-24T18:55:07.627671Z"
    assert _id_at(base) != _id_at(plus_1us)

    # Same via datetime objects, and stable across the string/datetime boundary.
    d0 = datetime(2026, 7, 24, 18, 55, 7, 627670, tzinfo=UTC)
    d1 = d0 + timedelta(microseconds=1)
    assert _id_at(d0) != _id_at(d1)
    assert _id_at(d0) == _id_at(base)


def test_one_microsecond_apart_recordings_coexist(db_path: Path):
    """End-to-end: two recordings 1 µs apart insert separately, no conflict."""
    first = _record(db_path, decision_at="2026-07-24T18:55:07.627670Z")
    second = _record(db_path, decision_at="2026-07-24T18:55:07.627671Z")

    assert second.context_hash == first.context_hash
    assert set(second.recommendation_ids).isdisjoint(first.recommendation_ids)
    assert len(second.inserted_ids) == 1
    assert second.reused_ids == ()
    assert _count(db_path, "recommendations") == 2
