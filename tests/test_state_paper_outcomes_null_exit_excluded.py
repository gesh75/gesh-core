"""NULL ``paper_outcomes.exit_at`` must not drive the daily-loss breaker.

#85 pins OPEN ``paper_trades`` (NULL exit_time). The tracker book uses
``exit_at >= todayT00:00:00+00:00``; a NULL compare is unknown and the row
is dropped. A placeholder ``pnl_usd`` on an unclosed outcome must not trip
the PAPER circuit breaker.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def test_null_exit_at_placeholder_pnl_is_excluded() -> None:
    state.init_trading_tables()
    today = datetime.now(UTC).strftime("%Y-%m-%d") + "T12:00:00+00:00"
    with state._conn() as con:
        con.execute("CREATE TABLE paper_outcomes (pnl_usd REAL, exit_at TEXT)")
        con.execute("INSERT INTO paper_outcomes VALUES (?, ?)", (-999.0, None))
        con.execute("INSERT INTO paper_outcomes VALUES (?, ?)", (-40.0, today))
    assert state.paper_realized_pnl_usd_today() == pytest.approx(-40.0)
