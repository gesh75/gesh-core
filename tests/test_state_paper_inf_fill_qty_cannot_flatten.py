"""+Inf SIMULATED fill_qty opens an uncloseable paper position.

``qty <= 0`` is False for +inf, so the book records qty=inf. A later SELL of
any finite size leaves inf shares — paper sizing then thinks the name is
still open and will keep emitting closes.
"""

from __future__ import annotations

import math

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


def test_inf_fill_qty_survives_finite_sell(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    _sim_fill("NVDA", "BUY", 10.0, 100.0, "buy-finite")
    _sim_fill("NVDA", "BUY", float("inf"), 100.0, "buy-inf")
    _sim_fill("NVDA", "SELL", 10.0, 110.0, "sell-10")

    book = state.paper_open_positions()
    assert "NVDA" in book
    assert math.isinf(book["NVDA"]["qty"])
