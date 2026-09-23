"""A SELL with no open qty is ignored — it must not invent a short or poison the next BUY."""

from __future__ import annotations

from gesh_core.trading import state


def _sim_fill(symbol: str, action: str, qty: float, price: float, coid: str) -> None:
    iid = state.log_intent({"symbol": symbol, "action": action, "confidence": 1.0, "source": "m"})
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


def test_orphan_sell_does_not_open_or_poison_book(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    _sim_fill("NVDA", "SELL", 5.0, 100.0, "orphan-sell")
    assert state.paper_open_positions() == {}

    _sim_fill("NVDA", "BUY", 10.0, 80.0, "later-buy")
    book = state.paper_open_positions()
    assert book["NVDA"]["qty"] == 10.0
    assert book["NVDA"]["avg_cost"] == 80.0
    assert book["NVDA"]["cost_basis"] == 800.0
