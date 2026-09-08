"""Falsy cost basis must surface as NO_COST_BASIS, never a fabricated $0 loss.

``if not _cb`` treats 0.0 / "" / False as missing. A map entry of 0.0 is also
falsy, so ``cbm.get(ticker) or pos.get(...)`` falls through to the position
basis instead of recording NO_COST_BASIS. Pin both so a later fail-closed
change is reviewable and a silent `or 0` cannot hide a real loss.
"""
from __future__ import annotations

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)


@pytest.mark.parametrize("basis", [0, 0.0, "", False])
def test_falsy_position_cost_basis_is_no_cost_basis_not_zeroed(basis):
    positions = {"ZZZ": {"price": 10.0, "quantity": 20, "average_buy_price": basis}}
    cands = th.scan_tax_loss_candidates(positions)
    assert len(cands) == 1
    rec = cands[0]
    assert rec["status"] == "NO_COST_BASIS"
    assert rec["cost_basis"] is None
    assert rec["unrealised_loss_usd"] is None


def test_zero_map_basis_falls_through_to_position_average():
    positions = {"EEE": {"price": 50.0, "quantity": 100, "average_buy_price": 100.0}}
    cands = th.scan_tax_loss_candidates(positions, cost_basis_map={"EEE": 0.0})
    rec = cands[0]
    assert rec["status"] == "ELIGIBLE"
    assert rec["cost_basis"] == pytest.approx(100.0)
    assert rec["unrealised_loss_usd"] == pytest.approx(-5000.0)
