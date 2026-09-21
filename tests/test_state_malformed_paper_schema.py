"""R3 leftover: only a missing table is skippable.

A present paper book with the wrong columns is a schema error, not a
fabricated $0 day and not LedgerUnavailable. Fail closed so the daily-loss
breaker cannot run on a broken ledger.
"""

from __future__ import annotations

import sqlite3

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")


@pytest.mark.parametrize(
    "ddl",
    [
        "CREATE TABLE paper_outcomes (wrong REAL)",
        "CREATE TABLE paper_trades (wrong REAL)",
    ],
)
def test_paper_realized_pnl_wrong_column_raises(ddl: str) -> None:
    state.init_trading_tables()
    with state._conn() as con:
        con.execute(ddl)
    with pytest.raises(sqlite3.OperationalError) as exc:
        state.paper_realized_pnl_usd_today()
    assert "no such column" in str(exc.value).lower()
    assert "LedgerUnavailable" not in type(exc.value).__name__
