"""Leftover daily-cap counter: ADD/TRIM do not consume approved_only capacity.

count_orders_today drives the max-orders-per-day breaker. It counts BUY/SELL
with a positive qty. ADD is a real entry action at the allocation gate; if it
started consuming (or stopped being excluded) the daily cap would silently
loosen or tighten. Pin the current action filter.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    state.init_trading_tables()


def _insert(*, client_order_id: str, action: str, status: str = "SIMULATED") -> None:
    with state._conn() as con:
        con.execute(
            """
            INSERT INTO orders
              (placed_at, intent_id, mode, client_order_id, status, symbol,
               action, qty, fill_qty)
            VALUES (?, 1, 'paper', ?, ?, 'TEST', ?, 1.0, 1.0)
            """,
            ("2026-08-04T16:00:00+00:00", client_order_id, status, action),
        )


def test_add_and_trim_are_excluded_from_approved_only_cap() -> None:
    now = datetime(2026, 8, 4, 12, tzinfo=ZoneInfo("America/New_York"))
    _insert(client_order_id="buy", action="BUY")
    _insert(client_order_id="sell", action="SELL")
    _insert(client_order_id="add", action="ADD")
    _insert(client_order_id="trim", action="TRIM")

    assert state.count_orders_today(now=now) == 2
    assert state.count_orders_today(approved_only=False, now=now) == 4
