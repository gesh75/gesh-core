"""ADD/TRIM paper fills must not invent or shrink the reconstructed book.

``validate_action`` accepts ADD/TRIM, but ``paper_open_positions`` only nets
BUY/SELL SIMULATED fills. Treating ADD as BUY (or TRIM as SELL) would
double-count qty and size the next close against a phantom position.
"""

from __future__ import annotations

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def _fill(*, symbol: str, action: str, fill_qty: float, fill_price: float, coid: str) -> None:
    iid = state.log_intent(
        {"symbol": symbol, "action": action, "confidence": 1.0, "source": "test"}
    )
    state.log_order(
        iid,
        None,
        "paper",
        coid,
        "SIMULATED",
        symbol,
        action,
        qty=fill_qty,
        target_price=fill_price,
        fill_price=fill_price,
        fill_qty=fill_qty,
    )


def test_add_and_trim_simulated_fills_do_not_open_or_change_book() -> None:
    state.init_trading_tables()
    _fill(symbol="NVDA", action="ADD", fill_qty=10, fill_price=100.0, coid="add")
    _fill(symbol="NVDA", action="TRIM", fill_qty=4, fill_price=110.0, coid="trim")
    assert state.paper_open_positions() == {}


def test_add_after_buy_does_not_increase_qty() -> None:
    state.init_trading_tables()
    _fill(symbol="HOOD", action="BUY", fill_qty=8, fill_price=50.0, coid="buy")
    _fill(symbol="HOOD", action="ADD", fill_qty=8, fill_price=55.0, coid="add")
    book = state.paper_open_positions()
    assert book["HOOD"]["qty"] == 8.0
    assert book["HOOD"]["avg_cost"] == pytest.approx(50.0)
