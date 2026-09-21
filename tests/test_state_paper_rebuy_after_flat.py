"""Leftover paper-book reconstruction: a flat name can be reopened.

#76 pins oversell-to-flat omission. After an exact close the next BUY must start
a fresh average-cost lot — otherwise leftover cost_basis dust (or a stale avg)
sizes the next SELL against the previous entry.
"""

from __future__ import annotations

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    state.init_trading_tables()


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


def test_rebuy_after_exact_close_uses_new_fill_as_avg_cost() -> None:
    _fill(symbol="AAPL", action="BUY", fill_qty=5.0, fill_price=200.0, coid="b1")
    _fill(symbol="AAPL", action="SELL", fill_qty=5.0, fill_price=210.0, coid="s1")
    assert "AAPL" not in state.paper_open_positions()

    _fill(symbol="AAPL", action="BUY", fill_qty=2.0, fill_price=50.0, coid="b2")
    book = state.paper_open_positions()
    assert book["AAPL"]["qty"] == 2.0
    assert book["AAPL"]["cost_basis"] == 100.0
    assert book["AAPL"]["avg_cost"] == 50.0
