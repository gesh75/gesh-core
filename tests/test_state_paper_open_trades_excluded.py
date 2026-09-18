"""Open paper_trades rows must not drive the daily-loss breaker.

The product book only sums rows with ``exit_time IS NOT NULL``. An OPEN
row with a placeholder realized_pnl would otherwise fabricate today's loss
and trip the PAPER circuit breaker.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def test_open_paper_trades_with_placeholder_pnl_are_excluded() -> None:
    state.init_trading_tables()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    with state._conn() as con:
        con.execute("CREATE TABLE paper_trades (realized_pnl REAL, exit_time TEXT)")
        con.execute(
            "INSERT INTO paper_trades VALUES (?, ?)",
            (-999.0, None),
        )
        con.execute(
            "INSERT INTO paper_trades VALUES (?, ?)",
            (-40.0, today + " 15:00"),
        )
    assert state.paper_realized_pnl_usd_today() == pytest.approx(-40.0)
