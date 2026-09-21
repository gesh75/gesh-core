"""paper_realized_pnl_usd_today when only the product paper_trades book exists.

The engine path (paper_outcomes only) is pinned on main. The product daily
chain writes paper_trades and may have no paper_outcomes table at all —
the breaker must still see today's closed PnL and ignore open rows.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def _today_date() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def test_product_like_book_uses_paper_trades_when_outcomes_missing() -> None:
    state.init_trading_tables()
    today = _today_date()
    with state._conn() as con:
        con.execute(
            "CREATE TABLE paper_trades (realized_pnl REAL, exit_time TEXT)"
        )
        con.execute(
            "INSERT INTO paper_trades VALUES (?, ?)",
            (-40.0, today + " 10:00"),
        )
        con.execute(
            "INSERT INTO paper_trades VALUES (?, ?)",
            (-999.0, None),  # still open — must not count
        )
        con.execute(
            "INSERT INTO paper_trades VALUES (?, ?)",
            (-80.0, "2020-01-01 10:00"),  # other day
        )
    assert state.paper_realized_pnl_usd_today() == pytest.approx(-40.0)
