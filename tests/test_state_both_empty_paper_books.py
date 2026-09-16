"""R3 leftover: two empty books are a measured $0 day, not unavailable.

Missing BOTH tables raises LedgerUnavailable. An engine+product DB that
created both schemas but has no closed rows today is a flat day.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def test_both_empty_paper_books_are_zero_not_unavailable() -> None:
    state.init_trading_tables()
    with state._conn() as con:
        con.execute("CREATE TABLE paper_outcomes (pnl_usd REAL, exit_at TEXT)")
        con.execute("CREATE TABLE paper_trades (realized_pnl REAL, exit_time TEXT)")
    assert state.paper_realized_pnl_usd_today() == 0.0


def test_null_realized_pnl_rows_count_as_zero() -> None:
    state.init_trading_tables()
    today = datetime.now(UTC).strftime("%Y-%m-%d") + "T12:00:00+00:00"
    with state._conn() as con:
        con.execute("CREATE TABLE paper_outcomes (pnl_usd REAL, exit_at TEXT)")
        con.execute("INSERT INTO paper_outcomes VALUES (?, ?)", (None, today))
    # SUM of NULL is NULL; COALESCE must keep this a measured $0, not raise.
    assert state.paper_realized_pnl_usd_today() == 0.0
