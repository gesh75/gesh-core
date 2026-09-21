"""``paper_open_positions`` is the paper-mode source of truth for sizing.

Only SIMULATED paper fills count. REJECTED/ERROR audit rows must not invent
qty, oversells must not go negative, and a flat-closed name must disappear
from the book. Ticker-case netting is claimed by the open production-fix PR.
"""

from __future__ import annotations

from gesh_core.trading import state


def _fill(
    *,
    symbol: str,
    action: str,
    fill_qty: float,
    fill_price: float,
    status: str = "SIMULATED",
    mode: str = "paper",
    client_order_id: str,
) -> None:
    iid = state.log_intent(
        {"symbol": symbol, "action": action, "confidence": 1.0, "source": "test"}
    )
    state.log_order(
        iid,
        None,
        mode,
        client_order_id,
        status,
        symbol,
        action,
        qty=fill_qty,
        target_price=fill_price,
        fill_price=fill_price,
        fill_qty=fill_qty,
    )


def test_simulated_buys_and_partial_sell_use_average_cost(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    state.init_trading_tables()
    _fill(symbol="NVDA", action="BUY", fill_qty=10, fill_price=100.0, client_order_id="b1")
    _fill(symbol="NVDA", action="SELL", fill_qty=4, fill_price=120.0, client_order_id="s1")

    book = state.paper_open_positions()
    assert book["NVDA"]["qty"] == 6.0
    assert book["NVDA"]["cost_basis"] == 600.0
    assert book["NVDA"]["avg_cost"] == 100.0


def test_rejected_and_error_fills_do_not_open_a_position(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    state.init_trading_tables()
    _fill(
        symbol="HOOD",
        action="BUY",
        fill_qty=50,
        fill_price=10.0,
        status="REJECTED",
        client_order_id="rej",
    )
    _fill(
        symbol="HOOD",
        action="BUY",
        fill_qty=50,
        fill_price=10.0,
        status="ERROR",
        client_order_id="err",
    )
    assert state.paper_open_positions() == {}


def test_oversell_is_capped_and_flat_position_omitted(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    state.init_trading_tables()
    _fill(symbol="AAPL", action="BUY", fill_qty=5, fill_price=200.0, client_order_id="b2")
    _fill(symbol="AAPL", action="SELL", fill_qty=99, fill_price=1.0, client_order_id="s2")
    assert "AAPL" not in state.paper_open_positions()


def test_zero_fill_qty_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    state.init_trading_tables()
    _fill(symbol="MSFT", action="BUY", fill_qty=0, fill_price=400.0, client_order_id="z")
    assert state.paper_open_positions() == {}
