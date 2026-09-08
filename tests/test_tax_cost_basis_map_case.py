"""cost_basis_map keys are looked up after ticker.upper() — lowercase misses.

A broker map keyed ``aapl`` silently becomes NO_COST_BASIS even when the
position ticker is ``AAPL`` / ``aapl``. The uppercase map key is the one
that actually applies. Pin the case fold so harvest eligibility cannot
drift if a host starts passing mixed-case maps.
"""

from __future__ import annotations

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)


def test_lowercase_map_key_misses_after_ticker_upper():
    positions = {"aapl": {"price": 50.0, "quantity": 100}}
    missed = th.scan_tax_loss_candidates(positions, cost_basis_map={"aapl": 100.0})
    assert missed[0]["ticker"] == "AAPL"
    assert missed[0]["status"] == "NO_COST_BASIS"
    assert missed[0]["unrealised_loss_usd"] is None


def test_uppercase_map_key_applies_to_mixed_case_position():
    positions = {"aapl": {"price": 50.0, "quantity": 100}}
    hit = th.scan_tax_loss_candidates(positions, cost_basis_map={"AAPL": 100.0})
    assert hit[0]["status"] == "ELIGIBLE"
    assert hit[0]["unrealised_loss_usd"] == pytest.approx(-5000.0)
