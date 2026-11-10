"""Empty-string exit_time is not a closed trade — must not count toward daily PnL."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from gesh_core.trading import state


def test_blank_exit_time_is_excluded_from_daily_pnl(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    now = datetime(2026, 8, 4, 16, tzinfo=ZoneInfo("America/New_York"))

    state.init_trading_tables()
    with state._conn() as con:
        con.execute("CREATE TABLE paper_trades (realized_pnl REAL, exit_time TEXT)")
        con.execute("INSERT INTO paper_trades VALUES (?, ?)", (-999.0, ""))
        con.execute(
            "INSERT INTO paper_trades VALUES (?, ?)",
            (-25.0, "2026-08-04T15:00:00+00:00"),
        )

    assert state.paper_realized_pnl_usd_today(now=now) == -25.0
