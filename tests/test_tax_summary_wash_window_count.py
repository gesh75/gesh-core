"""Harvest summary counts IN_WASH_WINDOW separately from ELIGIBLE.

``get_harvest_summary`` is the dashboard payload. A name inside the 30-day
window must increment ``in_wash_window_count`` and must not be summed into
``total_harvestable_loss_usd``.
"""

from __future__ import annotations

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)
    yield


def test_summary_counts_active_wash_window_and_excludes_it_from_total():
    th.record_harvest("GGG", sale_price=80.0, loss_usd=400.0)
    positions = {
        "H1": {"price": 50.0, "quantity": 100, "average_buy_price": 120.0},  # -$7000 ELIGIBLE
        "GGG": {"price": 80.0, "quantity": 10, "average_buy_price": 120.0},  # in window
    }
    out = th.get_harvest_summary(positions)
    assert out["eligible_count"] == 1
    assert out["in_wash_window_count"] == 1
    assert out["total_harvestable_loss_usd"] == pytest.approx(7000.0)
    assert out["eligible"][0]["ticker"] == "H1"
    assert out["in_wash_window"][0]["ticker"] == "GGG"
    assert "1 in 30-day" in out["summary"]
