"""Caller-supplied ``min_loss_usd`` is the eligibility threshold.

Dashboard and autopilot paths pass a floor; a regression that ignored the
argument would harvest (or hide) the wrong names relative to the $500 default.
Exact equality is eligible (``>=``).
"""

from __future__ import annotations

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)
    yield


def test_zero_floor_makes_a_tiny_loss_eligible():
    # $21 loss is BELOW_THRESHOLD at the $500 default.
    positions = {"CCC": {"price": 99.0, "quantity": 1, "average_buy_price": 120.0}}
    assert th.scan_tax_loss_candidates(positions)[0]["status"] == "BELOW_THRESHOLD"
    rec = th.scan_tax_loss_candidates(positions, min_loss_usd=0)[0]
    assert rec["status"] == "ELIGIBLE"
    assert rec["unrealised_loss_usd"] == pytest.approx(-21.0)


def test_raised_floor_demotes_a_default_eligible_loss():
    # $800 loss is ELIGIBLE at $500; a $1000 caller floor must hide it.
    positions = {"BBB": {"price": 80.0, "quantity": 20, "average_buy_price": 120.0}}
    assert th.scan_tax_loss_candidates(positions)[0]["status"] == "ELIGIBLE"
    rec = th.scan_tax_loss_candidates(positions, min_loss_usd=1000)[0]
    assert rec["status"] == "BELOW_THRESHOLD"


def test_loss_exactly_at_the_floor_is_eligible():
    # 10 shares * $50 gap = $500 — the default floor, inclusive.
    positions = {"EEE": {"price": 50.0, "quantity": 10, "average_buy_price": 100.0}}
    rec = th.scan_tax_loss_candidates(positions, min_loss_usd=500)[0]
    assert rec["unrealised_loss_usd"] == pytest.approx(-500.0)
    assert rec["status"] == "ELIGIBLE"
