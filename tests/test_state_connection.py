"""Caller-owned connection + fail-closed insert IDs in trading.state.

The main audit-chain tests use the module-owned connection. Autopilot and the
daily chain pass an open SQLite connection so intent/decision/order stay in
one transaction; a None lastrowid must raise rather than return a fake id.
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
    "canonical_key": "nvda-buy-1",
}


def test_log_and_get_intent_on_caller_connection():
    state.init_trading_tables()
    with state._conn() as con:
        iid = state.log_intent(_INTENT, connection=con)
        assert iid > 0
        row = state.get_intent_by_canonical_key("nvda-buy-1", connection=con)
        assert row is not None
        assert row["symbol"] == "NVDA"
        assert row["canonical_key"] == "nvda-buy-1"
        assert state.get_intent_by_canonical_key("missing", connection=con) is None


def test_insert_intent_fails_closed_when_lastrowid_missing():
    class _NoRowId:
        lastrowid = None

    class _Conn:
        def execute(self, *_a, **_k):
            return _NoRowId()

    with pytest.raises(sqlite3.DatabaseError, match="no row ID"):
        state._insert_intent(_Conn(), _INTENT)
