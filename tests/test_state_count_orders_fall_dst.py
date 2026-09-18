"""The daily order cap must use the 25-hour ET day on the fall DST boundary.

Spring (23-hour) bounds are pinned on main. November 1, 2026 falls back from
EDT to EST, so the America/New_York calendar day is [04:00Z, next 05:00Z).
A one-hour miss either side would under- or over-count live capacity.
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


def _insert_order(*, placed_at: str, client_order_id: str) -> None:
    state.init_trading_tables()
    with state._conn() as con:
        con.execute(
            """
            INSERT INTO orders
              (placed_at, intent_id, mode, client_order_id, status, symbol,
               action, qty, fill_qty)
            VALUES (?, 1, 'paper', ?, 'SIMULATED', 'TEST', 'BUY', 1.0, NULL)
            """,
            (placed_at, client_order_id),
        )


def test_count_orders_today_uses_et_fall_dst_25_hour_bounds() -> None:
    now = datetime(2026, 11, 1, 12, tzinfo=ZoneInfo("America/New_York"))
    _insert_order(placed_at="2026-11-01T03:59:59+00:00", client_order_id="before")
    _insert_order(placed_at="2026-11-01T04:00:00+00:00", client_order_id="lower")
    _insert_order(placed_at="2026-11-02T04:59:59+00:00", client_order_id="inside")
    _insert_order(placed_at="2026-11-02T05:00:00+00:00", client_order_id="upper")

    assert state.count_orders_today(now=now) == 2
