"""Broker payloads sometimes send ``shares`` instead of ``quantity``.
The scanner must still compute the unrealised loss; dropping the alias
would hide an ELIGIBLE harvest as if the position did not exist.
"""
from __future__ import annotations

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)
    yield


def test_shares_alias_when_quantity_missing():
    positions = {"BBB": {"price": 80.0, "shares": 20, "average_buy_price": 120.0}}
    cands = th.scan_tax_loss_candidates(positions)
    assert len(cands) == 1
    rec = cands[0]
    assert rec["ticker"] == "BBB"
    assert rec["shares"] == 20.0
    assert rec["unrealised_loss_usd"] == pytest.approx(-800.0)
    assert rec["status"] == "ELIGIBLE"


def test_quantity_wins_over_shares_when_both_present():
    # quantity=20 is the $800 ELIGIBLE loss; shares=1 would be BELOW_THRESHOLD.
    positions = {
        "BBB": {
            "price": 80.0,
            "quantity": 20,
            "shares": 1,
            "average_buy_price": 120.0,
        }
    }
    rec = th.scan_tax_loss_candidates(positions)[0]
    assert rec["shares"] == 20.0
    assert rec["status"] == "ELIGIBLE"
