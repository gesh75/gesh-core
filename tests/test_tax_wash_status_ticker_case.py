"""Wash-sale lookups upper-case the ticker — mixed-case reads hit the same row.

record_harvest stores ticker.upper(). get_wash_status must resolve "fff"
to the "FFF" window so a host that passes the broker's display case cannot
re-buy inside the IRS window.
"""
from __future__ import annotations

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)


def test_lowercase_lookup_finds_uppercased_harvest():
    th.record_harvest("fff", sale_price=10.0, loss_usd=600.0)
    status = th.get_wash_status("FfF")
    assert status["in_wash_window"] is True
    assert status["days_remaining"] > 0
