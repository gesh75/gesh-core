"""+Inf SIMULATED fill_price keeps the shares and poisons average cost.

NULL fill_price is excluded by SQL. +inf is a stored REAL, so the book
opens at inf cost_basis — any later SELL/PnL math inherits that poison.
"""

from __future__ import annotations

import math

from gesh_core.trading import state


def test_inf_fill_price_sets_inf_avg_cost(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    iid = state.log_intent({"symbol": "HOOD", "action": "BUY", "confidence": 1.0, "source": "m"})
    state.log_order(
        iid,
        None,
        "paper",
        "buy-inf-px",
        "SIMULATED",
        "HOOD",
        "BUY",
        10.0,
        12.5,
        fill_price=float("inf"),
        fill_qty=10.0,
    )

    book = state.paper_open_positions()
    assert book["HOOD"]["qty"] == 10.0
    assert math.isinf(book["HOOD"]["cost_basis"])
    assert math.isinf(book["HOOD"]["avg_cost"])
