"""init_db() must bootstrap Phase 4A ledger tables in the same SQLite file.

Hosts that only call ``db.init_db()`` (not ``init_ledger_tables`` themselves)
rely on this side effect. If it regresses, recommendation FK writes fail or the
ledger silently never exists beside analysis/paper tables.
"""
from __future__ import annotations

import sqlite3

from gesh_core import db

LEDGER_TABLES = {
    "portfolio_snapshots",
    "market_quote_snapshots",
    "recommendations",
}


def _table_names(path) -> set[str]:
    con = sqlite3.connect(str(path))
    try:
        return {
            row[0]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        con.close()


def test_init_db_creates_ledger_tables_in_shared_db(tmp_path, monkeypatch):
    path = tmp_path / "gesh_financial.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()

    names = _table_names(path)
    assert LEDGER_TABLES <= names
    # Core analysis/paper tables share the same file (daily-loss breaker contract).
    assert {"analysis_runs", "equity_snapshots", "paper_trades"} <= names


def test_init_db_ledger_bootstrap_is_idempotent(tmp_path, monkeypatch):
    path = tmp_path / "gesh_financial.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()
    db.init_db()
    assert LEDGER_TABLES <= _table_names(path)
