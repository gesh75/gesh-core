"""Daily order-cap window must refuse a naive ``now``.

``count_orders_today`` bounds the America/New_York calendar day. A naive
datetime would be treated as local wall time and mis-count the cap around
DST transitions — the same class of defect the existing ET-midnight tests
already pin for *aware* instants.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def test_count_orders_today_rejects_naive_now() -> None:
    state.init_trading_tables()
    with pytest.raises(ValueError, match="timezone-aware"):
        state.count_orders_today(now=datetime(2026, 1, 15, 12, 0))


def test_count_orders_today_accepts_aware_utc_now() -> None:
    state.init_trading_tables()
    assert state.count_orders_today(now=datetime(2026, 1, 15, 17, 0, tzinfo=UTC)) == 0
