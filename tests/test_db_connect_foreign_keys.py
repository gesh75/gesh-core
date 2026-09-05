"""db.connect() is the shared SQLite opener. Ledger FK constraints are only
enforced when foreign_keys=ON (SQLite defaults OFF). An all-invalid equity
snapshot must be a no-op so ECG/history are never poisoned with $0 rows.
"""
from __future__ import annotations

import pytest

from gesh_core import db


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "gesh_financial.db")
    db.init_db()
    yield


def test_connect_enables_foreign_keys(tmp_path):
    con = db.connect(str(tmp_path / "fk.db"))
    try:
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        con.close()


def test_equity_snapshot_all_invalid_is_noop(capsys):
    db.log_equity_snapshot(
        [
            {"symbol": "ZERO", "equity": 100, "current_price": 0},
            {"symbol": "NAN", "equity": 100, "current_price": float("nan")},
        ]
    )
    assert db.get_all_latest_snapshots() == []
    assert db.get_equity_history("ZERO") == []
    warning = capsys.readouterr().out
    assert "ZERO" in warning and "NAN" in warning
