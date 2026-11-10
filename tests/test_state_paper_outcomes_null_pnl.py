"""NULL pnl_usd on a closed paper_outcomes row is ignored by SUM, not a fabricated loss."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from gesh_core.trading import state


def test_null_pnl_usd_does_not_invent_daily_loss(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    now = datetime(2026, 8, 4, 16, tzinfo=ZoneInfo("America/New_York"))

    state.init_trading_tables()
    with state._conn() as con:
        con.execute("CREATE TABLE paper_outcomes (pnl_usd REAL, exit_at TEXT)")
        con.execute(
            "INSERT INTO paper_outcomes VALUES (?, ?)",
            (None, "2026-08-04T16:00:00+00:00"),
        )
        con.execute(
            "INSERT INTO paper_outcomes VALUES (?, ?)",
            (-40.0, "2026-08-04T16:00:00+00:00"),
        )

    assert state.paper_realized_pnl_usd_today(now=now) == -40.0
