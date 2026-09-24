"""NaN fill_qty / fill_price stored through log_order do not open a paper book.

SQLite persists Python NaN as NULL, and paper_open_positions already requires
``fill_qty IS NOT NULL AND fill_price IS NOT NULL``. A pandas NaN fill must
not create a phantom lot (and must not block a later finite fill).
"""

from __future__ import annotations

from gesh_core.trading import state


def _sim_fill(
    symbol: str,
    action: str,
    qty: float,
    price: float,
    coid: str,
    *,
    fill_qty: float,
    fill_price: float,
) -> None:
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
        fill_price=fill_price,
        fill_qty=fill_qty,
    )


def test_nan_fill_qty_does_not_open_or_poison_later_lot(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    _sim_fill(
        "NVDA",
        "BUY",
        10.0,
        100.0,
        "nan-qty",
        fill_qty=float("nan"),
        fill_price=100.0,
    )
    assert state.paper_open_positions() == {}

    _sim_fill(
        "NVDA",
        "BUY",
        10.0,
        100.0,
        "finite",
        fill_qty=10.0,
        fill_price=100.0,
    )
    book = state.paper_open_positions()
    assert book["NVDA"]["qty"] == 10.0
    assert book["NVDA"]["avg_cost"] == 100.0


def test_nan_fill_price_does_not_open_book(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    _sim_fill(
        "HOOD",
        "BUY",
        8.0,
        12.5,
        "nan-px",
        fill_qty=8.0,
        fill_price=float("nan"),
    )
    assert state.paper_open_positions() == {}
