"""Wash-sale status is the newest harvest row, not the first.

A name can be harvested more than once. ``ORDER BY created_at DESC LIMIT 1``
must win: an expired earlier sale must not keep the window open, and a fresh
sale must not be shadowed by a stale closed row.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)
    yield


def _insert(*, ticker: str, wash_safe: date, created_at: str) -> None:
    th.init_wash_sale_table()
    sale = (wash_safe - timedelta(days=th.WASH_SALE_DAYS)).isoformat()
    with th._get_conn() as conn:
        conn.execute(
            """INSERT INTO wash_sale_log
               (ticker, sale_date, sale_price, loss_usd, wash_safe_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticker.upper(), sale, 80.0, 400.0, wash_safe.isoformat(), created_at),
        )


def test_newer_active_harvest_overrides_an_expired_one():
    _insert(
        ticker="NVDA",
        wash_safe=date.today() - timedelta(days=2),
        created_at="2020-01-01T00:00:00",
    )
    _insert(
        ticker="NVDA",
        wash_safe=date.today() + timedelta(days=10),
        created_at="2026-01-01T00:00:00",
    )
    status = th.get_wash_status("NVDA")
    assert status["in_wash_window"] is True
    assert status["days_remaining"] == 10


def test_newer_expired_harvest_clears_an_older_active_row():
    _insert(
        ticker="NVDA",
        wash_safe=date.today() + timedelta(days=10),
        created_at="2020-01-01T00:00:00",
    )
    _insert(
        ticker="NVDA",
        wash_safe=date.today() - timedelta(days=1),
        created_at="2026-01-01T00:00:00",
    )
    status = th.get_wash_status("NVDA")
    assert status["in_wash_window"] is False
    assert status["days_remaining"] == 0
