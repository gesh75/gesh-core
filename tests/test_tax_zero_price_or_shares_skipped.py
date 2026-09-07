"""Zero/negative price or share count is dropped with no harvest row.

``scan_tax_loss_candidates`` requires finite, strictly positive price and
shares. A stale $0 quote or a 0-share lot therefore vanishes — not
``NO_COST_BASIS``, not an error. A sibling eligible loss in the same book
must still surface. Pin the silent skip so a later status row cannot
silently start counting these as harvestable.
"""
from __future__ import annotations

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)
    yield


@pytest.mark.parametrize(
    "position",
    [
        {"price": 0.0, "quantity": 10, "average_buy_price": 100.0},
        {"price": 50.0, "quantity": 0, "average_buy_price": 100.0},
        {"price": -1.0, "quantity": 10, "average_buy_price": 100.0},
        {"price": 50.0, "quantity": -5, "average_buy_price": 100.0},
    ],
)
def test_nonpositive_price_or_shares_are_skipped(position: dict) -> None:
    assert th.scan_tax_loss_candidates({"BAD": position}) == []


def test_sibling_eligible_loss_still_surfaces() -> None:
    positions = {
        "ZERO": {"price": 0.0, "quantity": 10, "average_buy_price": 100.0},
        "OK": {"price": 50.0, "quantity": 20, "average_buy_price": 100.0},
    }
    cands = th.scan_tax_loss_candidates(positions)
    assert [c["ticker"] for c in cands] == ["OK"]
    assert cands[0]["status"] == "ELIGIBLE"
    summary = th.get_harvest_summary(positions)
    assert summary["eligible_count"] == 1
    assert summary["no_cost_basis_count"] == 0
