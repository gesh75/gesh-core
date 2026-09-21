"""Tax leftover: harvestable dollars are Decimal-quantized to cents.

A loss that is messy in binary float (0.1/0.2 style) must still land on
an exact cent — this is the wash-sale ledger of record (M4).
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


def test_binary_dust_loss_quantizes_to_cents() -> None:
    # 0.1 - 0.2 = -0.1 in decimal; * 3 shares = -0.30. Float would drift.
    positions = {"PEN": {"price": 0.1, "quantity": 3, "average_buy_price": 0.2}}
    cands = th.scan_tax_loss_candidates(positions, min_loss_usd=0.0)
    assert len(cands) == 1
    assert cands[0]["unrealised_loss_usd"] == pytest.approx(-0.30)
    assert cands[0]["status"] == "ELIGIBLE"


def test_two_dust_losses_sum_to_exact_cents() -> None:
    positions = {
        "A": {"price": 0.1, "quantity": 3, "average_buy_price": 0.2},  # -0.30
        "B": {"price": 1.15, "quantity": 2, "average_buy_price": 1.20},  # -0.10
    }
    cands = th.scan_tax_loss_candidates(positions, min_loss_usd=0.0)
    by_ticker = {c["ticker"]: c["unrealised_loss_usd"] for c in cands}
    assert by_ticker["A"] == pytest.approx(-0.30)
    assert by_ticker["B"] == pytest.approx(-0.10)
    total = sum((th._money(c["unrealised_loss_usd"]).copy_abs() for c in cands), Decimal(0))
    assert th._cents(total) == pytest.approx(0.40)
