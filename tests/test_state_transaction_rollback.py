"""trading.state._conn must roll back a partial audit write on exception.

A half-written intent→decision→order sequence corrupts execution forensics and
downstream daily-order counters. Success must commit; any raise must leave the
file unchanged.
"""
from __future__ import annotations

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
    "source": "test",
}


def test_conn_rolls_back_intent_insert_on_subsequent_failure():
    state.init_trading_tables()
    with pytest.raises(RuntimeError, match="boom"):
        with state._conn() as con:
            state._insert_intent(con, _INTENT)
            raise RuntimeError("boom")

    assert state.recent_intents() == []


def test_conn_commits_when_full_block_succeeds():
    state.init_trading_tables()
    with state._conn() as con:
        row_id = state._insert_intent(con, _INTENT)

    stored = state.recent_intents()
    assert len(stored) == 1
    assert stored[0]["id"] == row_id
    assert stored[0]["symbol"] == "NVDA"
