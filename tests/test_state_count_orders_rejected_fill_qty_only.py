"""REJECTED rows never consume the daily cap, even when only fill_qty is set."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from gesh_core.trading import state


def test_rejected_fill_qty_only_does_not_consume_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    now = datetime(2026, 8, 4, 12, tzinfo=ZoneInfo("America/New_York"))
    placed_at = "2026-08-04T16:00:00+00:00"

    state.init_trading_tables()
    with state._conn() as con:
        con.execute(
            """
            INSERT INTO orders
              (placed_at, intent_id, mode, client_order_id, status, symbol,
               action, qty, fill_qty)
            VALUES (?, 1, 'paper', 'rej-fill', 'REJECTED', 'TEST', 'BUY', ?, ?)
            """,
            (placed_at, 0.0, 5.0),
        )
        con.execute(
            """
            INSERT INTO orders
              (placed_at, intent_id, mode, client_order_id, status, symbol,
               action, qty, fill_qty)
            VALUES (?, 1, 'paper', 'ok-fill', 'SIMULATED', 'TEST', 'BUY', ?, ?)
            """,
            (placed_at, 1.0, 1.0),
        )

    assert state.count_orders_today(now=now) == 1
    assert state.count_orders_today(approved_only=False, now=now) == 2
