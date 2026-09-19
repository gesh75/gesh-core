"""Empty ``mode=""`` is falsy and does not filter the daily order cap.

Callers that pass a blank mode string intending "no paper/live mix" currently
count every mode. That silently inflates the shared daily cap.
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


def _insert(*, client_order_id: str, mode: str) -> None:
    state.init_trading_tables()
    with state._conn() as con:
        con.execute(
            """
            INSERT INTO orders
              (placed_at, intent_id, mode, client_order_id, status, symbol,
               action, qty, fill_qty)
            VALUES ('2026-08-04T16:00:00+00:00', 1, ?, ?, 'SIMULATED', 'TEST', 'BUY', 1.0, 1.0)
            """,
            (mode, client_order_id),
        )


def test_empty_mode_string_counts_every_mode() -> None:
    now = datetime(2026, 8, 4, 12, tzinfo=ZoneInfo("America/New_York"))
    _insert(client_order_id="paper", mode="paper")
    _insert(client_order_id="live", mode="live")

    assert state.count_orders_today(now=now) == 2
    assert state.count_orders_today(mode="paper", now=now) == 1
    assert state.count_orders_today(mode="", now=now) == 2
