"""Leftover paper-book reconstruction: only SIMULATED paper fills open qty.

#76 pins avg-cost, REJECTED/ERROR, and oversell-to-flat. Live fills, non-SIMULATED
audit statuses, and non-positive qty must still be invisible to sizing — otherwise
the paper book invents phantom positions the daily-loss breaker and SELL sizer
will trade against.
"""

from __future__ import annotations

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    state.init_trading_tables()


def _fill(
    *,
    symbol: str,
    action: str,
    fill_qty: float | None,
    fill_price: float | None,
    status: str = "SIMULATED",
    mode: str = "paper",
    client_order_id: str,
    qty: float | None = None,
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
        qty=qty if qty is not None else fill_qty,
        target_price=fill_price,
        fill_price=fill_price,
        fill_qty=fill_qty,
    )


@pytest.mark.parametrize(
    "status,mode,fill_qty,fill_price,client_order_id",
    [
        ("SUBMITTED", "paper", 10.0, 100.0, "sub"),
        ("FILLED", "paper", 10.0, 100.0, "fil"),
        ("SKIPPED", "paper", 10.0, 100.0, "skp"),
        ("SIMULATED", "live", 10.0, 100.0, "live"),
        ("SIMULATED", "paper", 0.0, 100.0, "zero"),
        ("SIMULATED", "paper", -4.0, 100.0, "neg"),
    ],
)
def test_non_simulated_or_non_paper_fills_do_not_open_a_position(
    status: str, mode: str, fill_qty: float, fill_price: float, client_order_id: str
) -> None:
    _fill(
        symbol="NVDA",
        action="BUY",
        fill_qty=fill_qty,
        fill_price=fill_price,
        status=status,
        mode=mode,
        client_order_id=client_order_id,
    )
    assert state.paper_open_positions() == {}


def test_simulated_paper_buy_still_opens_a_position() -> None:
    _fill(
        symbol="NVDA",
        action="BUY",
        fill_qty=10.0,
        fill_price=100.0,
        client_order_id="ok",
    )
    book = state.paper_open_positions()
    assert book["NVDA"]["qty"] == 10.0
    assert book["NVDA"]["avg_cost"] == 100.0
