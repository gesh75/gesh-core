"""BELOW_THRESHOLD losses are scanned but dropped from the dashboard summary.

get_harvest_summary only buckets ELIGIBLE / IN_WASH_WINDOW / NO_COST_BASIS.
A small realized-unrealised loss must not inflate eligible_count or the
harvestable total — and must not vanish from scan_tax_loss_candidates.
"""

from __future__ import annotations

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)


def test_below_threshold_is_scanned_but_omitted_from_summary_buckets():
    positions = {
        "TINY": {"price": 99.0, "quantity": 1, "average_buy_price": 120.0},  # -$21
        "BIG": {"price": 50.0, "quantity": 100, "average_buy_price": 120.0},  # eligible
    }
    scanned = th.scan_tax_loss_candidates(positions)
    statuses = {c["ticker"]: c["status"] for c in scanned}
    assert statuses["TINY"] == "BELOW_THRESHOLD"
    assert statuses["BIG"] == "ELIGIBLE"

    summary = th.get_harvest_summary(positions)
    assert summary["eligible_count"] == 1
    assert summary["no_cost_basis_count"] == 0
    assert [c["ticker"] for c in summary["eligible"]] == ["BIG"]
    assert all(c["status"] != "BELOW_THRESHOLD" for c in summary["eligible"])
    assert summary["total_harvestable_loss_usd"] == pytest.approx(7000.0)
