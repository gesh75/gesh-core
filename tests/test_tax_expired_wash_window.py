"""A wash-sale window that already ended must not keep blocking harvest.

``get_wash_status`` uses a strict ``wash_safe_date > today`` check. Day 30
(``== today``) is claimed by the open production-fix PR; this pins the
already-expired side so a later ``>=`` cannot keep a name locked out after
the IRS window has closed.
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


def _insert_harvest(*, ticker: str, wash_safe: date, sale: date | None = None) -> None:
    th.init_wash_sale_table()
    sale_date = (sale or (wash_safe - timedelta(days=th.WASH_SALE_DAYS))).isoformat()
    with th._get_conn() as conn:
        conn.execute(
            """INSERT INTO wash_sale_log
               (ticker, sale_date, sale_price, loss_usd, wash_safe_date)
               VALUES (?, ?, ?, ?, ?)""",
            (ticker.upper(), sale_date, 80.0, 400.0, wash_safe.isoformat()),
        )


def test_expired_wash_window_is_not_blocking():
    _insert_harvest(ticker="GGG", wash_safe=date.today() - timedelta(days=1))
    status = th.get_wash_status("GGG")
    assert status["in_wash_window"] is False
    assert status["days_remaining"] == 0
    assert status["wash_safe_date"] == (date.today() - timedelta(days=1)).isoformat()


def test_expired_window_lets_a_real_loss_be_eligible():
    _insert_harvest(ticker="GGG", wash_safe=date.today() - timedelta(days=1))
    positions = {"GGG": {"price": 80.0, "quantity": 20, "average_buy_price": 120.0}}
    cands = th.scan_tax_loss_candidates(positions)
    assert cands[0]["status"] == "ELIGIBLE"
    assert cands[0]["in_wash_window"] is False
