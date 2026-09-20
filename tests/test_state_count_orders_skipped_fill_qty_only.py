"""SKIPPED is not an actionable status — fill_qty-only must not consume the cap."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from gesh_core.trading import state


def test_skipped_fill_qty_only_does_not_consume_cap(tmp_path, monkeypatch):
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
            VALUES (?, 1, 'paper', 'skip-fill', 'SKIPPED', 'TEST', 'BUY', ?, ?)
            """,
            (placed_at, 0.0, 8.0),
        )

    assert state.count_orders_today(now=now) == 0
    assert state.count_orders_today(approved_only=False, now=now) == 1
