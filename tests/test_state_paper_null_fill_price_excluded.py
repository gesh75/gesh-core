"""NULL fill_price is excluded by the paper-book query — no undefined cost basis."""

from __future__ import annotations

from gesh_core.trading import state


def test_null_fill_price_does_not_open_position(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    iid = state.log_intent({"symbol": "NVDA", "action": "BUY", "confidence": 1.0, "source": "m"})
    state.log_order(
        iid,
        None,
        "paper",
        "null-px",
        "SIMULATED",
        "NVDA",
        "BUY",
        10.0,
        100.0,
        fill_price=None,
        fill_qty=10.0,
    )

    assert state.paper_open_positions() == {}
