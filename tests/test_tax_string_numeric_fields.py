"""Broker JSON often ships prices/qty as strings; the scanner must coerce them.

``float(pos.get(...))`` accepts ``"80.0"``. A later ``isinstance(..., (int, float))``
gate would silently drop every Robinhood string field and hide real losses.
"""

from __future__ import annotations

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)
    yield


def test_string_price_quantity_and_basis_still_scan():
    positions = {
        "BBB": {"price": "80.0", "quantity": "20", "average_buy_price": "120.0"},
    }
    cands = th.scan_tax_loss_candidates(positions)
    assert len(cands) == 1
    assert cands[0]["status"] == "ELIGIBLE"
    assert cands[0]["unrealised_loss_usd"] == pytest.approx(-800.0)


def test_non_numeric_string_price_currently_raises():
    # Broker "N/A" is not coerced to 0 and is not skipped — float() raises.
    # Pin the fail-loud path so a later silent-skip change is intentional.
    positions = {
        "BAD": {"price": "N/A", "quantity": 20, "average_buy_price": 120.0},
    }
    with pytest.raises(ValueError, match="N/A"):
        th.scan_tax_loss_candidates(positions)
