"""A partial SELL reduces qty at average cost and leaves the remainder open."""

from __future__ import annotations

from gesh_core.trading import state


def _sim_fill(symbol: str, action: str, qty: float, price: float, coid: str) -> None:
    iid = state.log_intent(
        {"symbol": symbol, "action": action, "confidence": 1.0, "source": "m"}
    )
    state.log_order(
        iid,
        None,
        "paper",
        coid,
        "SIMULATED",
        symbol,
        action,
        qty,
        price,
        fill_price=price,
        fill_qty=qty,
    )


def test_partial_sell_keeps_avg_cost_and_remaining_qty(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    _sim_fill("NVDA", "BUY", 10.0, 100.0, "buy-10")
    _sim_fill("NVDA", "SELL", 4.0, 120.0, "sell-4")

    book = state.paper_open_positions()
    assert book["NVDA"]["qty"] == 6.0
    assert book["NVDA"]["avg_cost"] == 100.0
    assert book["NVDA"]["cost_basis"] == 600.0
