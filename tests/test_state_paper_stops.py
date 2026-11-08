"""Paper-stop persistence for the EOD sweep.

Holdings never carry a stop_loss field. ``record_stop`` / ``active_stops`` /
``deactivate_stops`` are the only source of exit levels the close-scan reads.
Wrong later-wins or a stale active row after a full close misses or double-fires
exits.
"""

from __future__ import annotations

import sqlite3

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def test_record_stop_returns_row_id_and_is_active() -> None:
    state.init_trading_tables()
    row_id = state.record_stop(
        "NVDA",
        entry_price=100.0,
        stop_price=94.0,
        take_profit_price=110.0,
        volatility_tier="MEDIUM",
        order_row_id=7,
    )
    assert row_id >= 1
    stops = state.active_stops()
    assert set(stops) == {"NVDA"}
    nvda = stops["NVDA"]
    assert nvda["entry_price"] == pytest.approx(100.0)
    assert nvda["stop_price"] == pytest.approx(94.0)
    assert nvda["take_profit_price"] == pytest.approx(110.0)
    assert nvda["volatility_tier"] == "MEDIUM"
    assert nvda["order_row_id"] == 7
    assert nvda["active"] == 1


def test_later_stop_for_same_symbol_wins() -> None:
    state.init_trading_tables()
    state.record_stop("NVDA", entry_price=100.0, stop_price=94.0, take_profit_price=110.0)
    state.record_stop("NVDA", entry_price=105.0, stop_price=98.0, take_profit_price=116.0)
    nvda = state.active_stops()["NVDA"]
    assert nvda["entry_price"] == pytest.approx(105.0)
    assert nvda["stop_price"] == pytest.approx(98.0)
    assert nvda["take_profit_price"] == pytest.approx(116.0)


def test_deactivate_stops_retires_only_that_symbol() -> None:
    state.init_trading_tables()
    state.record_stop("NVDA", entry_price=100.0, stop_price=94.0)
    state.record_stop("AAPL", entry_price=150.0, stop_price=142.0)
    state.deactivate_stops("NVDA")
    stops = state.active_stops()
    assert "NVDA" not in stops
    assert stops["AAPL"]["stop_price"] == pytest.approx(142.0)


def test_deactivate_is_idempotent_and_init_does_not_drop_rows() -> None:
    state.init_trading_tables()
    state.record_stop("NVDA", entry_price=100.0, stop_price=94.0)
    state.deactivate_stops("NVDA")
    state.deactivate_stops("NVDA")
    state.init_trading_tables()
    assert state.active_stops() == {}
    with sqlite3.connect(state.DB_PATH) as con:
        row = con.execute("SELECT COUNT(*) AS n, SUM(active) AS live FROM paper_stops").fetchone()
    assert row[0] == 1
    assert row[1] == 0


def test_empty_book_has_no_active_stops() -> None:
    state.init_trading_tables()
    assert state.active_stops() == {}
