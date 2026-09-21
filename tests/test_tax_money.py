"""Cent-precise harvest math — leftover from the wash-sale coverage PR.

Wash-sale totals are a tax ledger of record. _money/_cents must coerce junk to
zero and round half-up to the cent so summed eligible losses stay exact.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)
    yield


def test_money_none_and_empty_are_zero():
    assert th._money(None) == Decimal("0")
    assert th._money("") == Decimal("0")
    assert th._money(0) == Decimal("0")


def test_cents_rounds_half_up():
    assert th._cents(Decimal("1.225")) == pytest.approx(1.23)
    assert th._cents(Decimal("1.224")) == pytest.approx(1.22)
    assert th._cents(Decimal("-1.225")) == pytest.approx(-1.23)


def test_harvest_summary_sums_eligible_losses_to_the_cent():
    positions = {
        "H1": {"price": 50.0, "quantity": 100, "average_buy_price": 120.0},  # -7000
        "H2": {"price": 10.0, "quantity": 100, "average_buy_price": 20.0},  # -1000
        "H3": {"price": 99.0, "quantity": 1, "average_buy_price": 120.0},  # below threshold
    }
    out = th.get_harvest_summary(positions)
    assert out["eligible_count"] == 2
    assert out["total_harvestable_loss_usd"] == pytest.approx(8000.0)
    assert "8000" in out["summary"] or "8,000" in out["summary"]
