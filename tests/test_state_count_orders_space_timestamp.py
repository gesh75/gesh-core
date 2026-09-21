"""Space-separated ``placed_at`` is excluded from the ET order-cap window.

``count_orders_today`` compares ISO text, not parsed instants. A broker or
legacy writer that stores ``2026-08-04 16:00:00+00:00`` (space, not ``T``)
sorts *before* the day's ``...T04:00:00+00:00`` bound, so the row does not
consume the daily cap — the cap fail-opens for that order.
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


def _insert(*, placed_at: str, client_order_id: str) -> None:
    state.init_trading_tables()
    with state._conn() as con:
        con.execute(
            """
            INSERT INTO orders
              (placed_at, intent_id, mode, client_order_id, status, symbol,
               action, qty, fill_qty)
            VALUES (?, 1, 'paper', ?, 'SIMULATED', 'TEST', 'BUY', 1.0, 1.0)
            """,
            (placed_at, client_order_id),
        )


def test_space_separated_placed_at_is_outside_et_iso_bounds() -> None:
    now = datetime(2026, 8, 4, 12, tzinfo=ZoneInfo("America/New_York"))
    _insert(placed_at="2026-08-04 16:00:00+00:00", client_order_id="space")
    _insert(placed_at="2026-08-04T16:00:00+00:00", client_order_id="iso")

    assert state.count_orders_today(now=now) == 1
    assert state.count_orders_today(approved_only=False, now=now) == 1
