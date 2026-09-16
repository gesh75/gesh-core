"""R3 leftover: a product-only paper_trades book is a measured loss.

Main pins outcomes-only (engine) and empty paper_trades = $0. The product
daily-analysis book is the other expected single-table layout — today's
realized_pnl must drive the daily-loss breaker, not raise LedgerUnavailable.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def test_paper_trades_only_with_today_loss_is_measured() -> None:
    state.init_trading_tables()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    with state._conn() as con:
        con.execute("CREATE TABLE paper_trades (realized_pnl REAL, exit_time TEXT)")
        con.execute(
            "INSERT INTO paper_trades VALUES (?, ?)",
            (-80.0, today + " 14:30"),
        )
    assert state.paper_realized_pnl_usd_today() == pytest.approx(-80.0)
