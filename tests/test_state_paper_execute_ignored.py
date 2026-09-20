"""EXECUTE is not BUY/SELL — SIMULATED EXECUTE fills must not open the paper book."""

from __future__ import annotations

from gesh_core.trading import state


def test_simulated_execute_does_not_open_book(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    iid = state.log_intent(
        {"symbol": "NVDA", "action": "BUY", "confidence": 1.0, "source": "m"}
    )
    state.log_order(
        iid,
        None,
        "paper",
        "exec-1",
        "SIMULATED",
        "NVDA",
        "EXECUTE",
        10.0,
        100.0,
        fill_price=100.0,
        fill_qty=10.0,
    )

    assert state.paper_open_positions() == {}
