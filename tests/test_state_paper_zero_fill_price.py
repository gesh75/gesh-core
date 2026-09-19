"""A $0 or negative SIMULATED fill_price still opens the paper book.

``paper_open_positions`` filters NULL fill_price / fill_qty and qty<=0, but
a present 0.0 or negative price is used as cost. Sizing and PnL against
avg_cost=0 (or a negative basis) is the next failure after a bad broker fill.
"""

from __future__ import annotations

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def _fill(*, symbol: str, fill_qty: float, fill_price: float, client_order_id: str) -> None:
    iid = state.log_intent(
        {"symbol": symbol, "action": "BUY", "confidence": 1.0, "source": "test"}
    )
    state.log_order(
        iid,
        None,
        "paper",
        client_order_id,
        "SIMULATED",
        symbol,
        "BUY",
        qty=fill_qty,
        target_price=fill_price,
        fill_price=fill_price,
        fill_qty=fill_qty,
    )


def test_zero_fill_price_opens_position_at_zero_avg_cost() -> None:
    _fill(symbol="ZERO", fill_qty=5.0, fill_price=0.0, client_order_id="z0")
    book = state.paper_open_positions()
    assert book["ZERO"]["qty"] == 5.0
    assert book["ZERO"]["cost_basis"] == 0.0
    assert book["ZERO"]["avg_cost"] == 0.0


def test_negative_fill_price_opens_position_with_negative_basis() -> None:
    _fill(symbol="NEG", fill_qty=2.0, fill_price=-10.0, client_order_id="n0")
    book = state.paper_open_positions()
    assert book["NEG"]["qty"] == 2.0
    assert book["NEG"]["cost_basis"] == -20.0
    assert book["NEG"]["avg_cost"] == -10.0
