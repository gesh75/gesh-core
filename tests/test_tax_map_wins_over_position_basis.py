"""When both sources are present, ``cost_basis_map`` wins over the position.

Main already covers map-only (no ``average_buy_price``). A stale position
basis that silently won would hide or inflate harvestable loss vs the
Robinhood avg-cost map the product passes in.
"""

from __future__ import annotations

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)
    yield


def test_cost_basis_map_overrides_average_buy_price_when_both_set() -> None:
    positions = {
        "EEE": {"price": 50.0, "quantity": 10.0, "average_buy_price": 200.0},
    }
    # vs map 80 → -$300 BELOW_THRESHOLD; vs position 200 → -$1,500 ELIGIBLE
    cands = th.scan_tax_loss_candidates(positions, cost_basis_map={"EEE": 80.0})
    assert len(cands) == 1
    assert cands[0]["cost_basis"] == pytest.approx(80.0)
    assert cands[0]["unrealised_loss_usd"] == pytest.approx(-300.0)
    assert cands[0]["status"] == "BELOW_THRESHOLD"
