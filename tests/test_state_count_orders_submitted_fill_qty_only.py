"""SUBMITTED with qty=0 and fill_qty>0 still consumes the daily order cap.

#85 pins ERROR qty=0 + fill_qty>0. Brokers also ack SUBMITTED / FILLED with
a zero submitted size and a positive fill. The COALESCE filter is the same
capacity rule — a missed SUBMITTED row fail-opens the cap after a live ack.
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


def _insert(*, client_order_id: str, status: str, qty: float | None, fill_qty: float | None) -> None:
    state.init_trading_tables()
    with state._conn() as con:
        con.execute(
            """
            INSERT INTO orders
              (placed_at, intent_id, mode, client_order_id, status, symbol,
               action, qty, fill_qty)
            VALUES ('2026-08-04T16:00:00+00:00', 1, 'live', ?, ?, 'TEST', 'BUY', ?, ?)
            """,
            (client_order_id, status, qty, fill_qty),
        )


@pytest.mark.parametrize("status", ["SUBMITTED", "FILLED"])
def test_zero_qty_positive_fill_qty_consumes_cap(status: str) -> None:
    now = datetime(2026, 8, 4, 12, tzinfo=ZoneInfo("America/New_York"))
    _insert(client_order_id=f"{status}-fill-only", status=status, qty=0.0, fill_qty=3.0)
    assert state.count_orders_today(mode="live", now=now) == 1
