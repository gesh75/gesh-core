"""Caller-owned connection for log_decision + fail-closed lastrowid.

Autopilot writes intent+decision in one transaction. log_intent on a
shared connection is already claimed; the decision insert is the other
half of that atomic pair. A None lastrowid must raise rather than return
a fake id that would orphan the order row.
"""
from __future__ import annotations

import sqlite3

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


_INTENT = {
    "symbol": "NVDA",
    "action": "BUY",
    "confidence": 0.9,
    "target_position_pct": 0.02,
    "source": "consensus",
}


def test_log_decision_on_caller_connection_is_visible_before_commit() -> None:
    state.init_trading_tables()
    with state._conn() as con:
        iid = state.log_intent(_INTENT, connection=con)
        did = state.log_decision(
            iid,
            "REJECTED",
            "CASH_FLOOR",
            {"CASH_FLOOR": False},
            {"paper_mode": True},
            connection=con,
        )
        assert did > 0
        row = con.execute("SELECT * FROM risk_decisions WHERE id = ?", (did,)).fetchone()
        assert row["intent_id"] == iid
        assert row["verdict"] == "REJECTED"
        assert row["reason"] == "CASH_FLOOR"


def test_log_decision_fails_closed_when_lastrowid_missing() -> None:
    class _NoRowId:
        lastrowid = None

    class _Conn:
        def execute(self, *_a, **_k):
            return _NoRowId()

    with pytest.raises(sqlite3.DatabaseError, match="no row ID"):
        state.log_decision(
            1,
            "APPROVED",
            None,
            {"KILL_SWITCH": True},
            {},
            connection=_Conn(),  # type: ignore[arg-type]
        )
