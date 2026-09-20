"""Paper book reconstruction must not mix cost basis across symbols."""

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


def test_two_symbols_keep_independent_avg_cost(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    _sim_fill("NVDA", "BUY", 2.0, 100.0, "nvda-buy")
    _sim_fill("HOOD", "BUY", 5.0, 20.0, "hood-buy")
    _sim_fill("NVDA", "SELL", 1.0, 110.0, "nvda-sell")

    book = state.paper_open_positions()
    assert set(book) == {"NVDA", "HOOD"}
    assert book["NVDA"]["qty"] == 1.0
    assert book["NVDA"]["avg_cost"] == 100.0
    assert book["HOOD"]["qty"] == 5.0
    assert book["HOOD"]["avg_cost"] == 20.0
    assert book["HOOD"]["cost_basis"] == 100.0
