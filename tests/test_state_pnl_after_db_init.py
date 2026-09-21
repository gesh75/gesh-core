"""R3 leftover: db.init_db creates paper_trades, so the breaker sees a measured $0.

The two-book design skips a missing table, but product bootstrap writes
paper_trades via db.py DDL. After that shared init, missing paper_outcomes
must not raise LedgerUnavailable — an empty present book is a flat day.
"""

from __future__ import annotations

from gesh_core import db
from gesh_core.trading import state


def test_paper_realized_pnl_after_db_init_is_measured_zero(tmp_path, monkeypatch) -> None:
    path = tmp_path / "gesh_financial.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setattr(state, "DB_PATH", path)
    db.init_db()
    assert state.paper_realized_pnl_usd_today() == 0.0
