"""Paper book reconstruction must use fill_qty, never the submitted qty.

A partial fill (submitted 100, filled 2) that counted the submitted size
would invent a 50× paper position and size the next SELL against phantom
shares — the same class of defect as reconstructing from REJECTED audit rows.
"""

from __future__ import annotations

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def test_paper_book_uses_fill_qty_not_submitted_qty() -> None:
    iid = state.log_intent(
        {"symbol": "NVDA", "action": "BUY", "confidence": 1.0, "source": "test"}
    )
    state.log_order(
        iid,
        None,
        "paper",
        "partial",
        "SIMULATED",
        "NVDA",
        "BUY",
        qty=100.0,
        target_price=50.0,
        fill_price=50.0,
        fill_qty=2.0,
    )

    book = state.paper_open_positions()
    assert book["NVDA"]["qty"] == 2.0
    assert book["NVDA"]["cost_basis"] == 100.0
    assert book["NVDA"]["avg_cost"] == 50.0
