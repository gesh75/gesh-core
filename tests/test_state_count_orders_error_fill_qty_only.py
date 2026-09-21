"""ERROR rows with qty=0 but a positive fill_qty still consume the daily cap.

Broker timeouts can persist submitted size on ``fill_qty`` while leaving
``qty`` at 0. Counting only ``qty > 0`` would under-count and admit another
live order after the broker already accepted one.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def test_error_with_zero_qty_and_positive_fill_qty_consumes_cap() -> None:
    now = datetime(2026, 8, 4, 12, tzinfo=ZoneInfo("America/New_York"))
    state.init_trading_tables()
    with state._conn() as con:
        con.execute(
            """
            INSERT INTO orders
              (placed_at, intent_id, mode, client_order_id, status, symbol,
               action, qty, fill_qty)
            VALUES (?, 1, 'live', 'err-fill', 'ERROR', 'TEST', 'BUY', 0.0, 3.0)
            """,
            ("2026-08-04T16:00:00+00:00",),
        )

    assert state.count_orders_today(mode="live", now=now) == 1
    assert state.count_orders_today(now=now) == 1
