"""Leftover audit-chain edges: missing canonical lookup and lastrowid fail-closed.

A missing canonical_key must return None (never invent a row). A decision insert
that reports no row ID must raise — the intent→decision chain is the execution
audit, and a silent None id would break every downstream FK.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def test_get_intent_by_canonical_key_missing_returns_none():
    state.init_trading_tables()
    assert state.get_intent_by_canonical_key("no-such-key") is None


def test_get_intent_by_canonical_key_missing_on_caller_connection_returns_none():
    state.init_trading_tables()
    with sqlite3.connect(state.DB_PATH) as con:
        assert state.get_intent_by_canonical_key("no-such-key", connection=con) is None


def test_log_decision_fails_closed_when_lastrowid_missing():
    con = MagicMock()
    con.execute.return_value.lastrowid = None
    with pytest.raises(sqlite3.DatabaseError, match="no row ID"):
        state.log_decision(
            1,
            "APPROVED",
            None,
            {"KILL_SWITCH": True},
            {"paper_mode": True},
            connection=con,
        )
