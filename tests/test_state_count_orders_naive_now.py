"""count_orders_today rejects a naive ``now`` so ET day bounds stay defined.

The daily order-rate cap is an America/New_York calendar window. A naive
datetime has no timezone to convert, so the function must raise rather than
treat wall-clock as UTC (or local) and mis-count the cap across DST.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def test_naive_now_raises():
    state.init_trading_tables()
    with pytest.raises(ValueError, match="timezone-aware"):
        state.count_orders_today(now=datetime(2026, 9, 2, 12, 0, 0))
