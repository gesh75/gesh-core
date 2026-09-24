"""NaN equity becomes SQL NULL and trips NOT NULL — the whole snapshot batch dies.

Price is validated and skipped; equity is written with ``h.get("equity", 0)``.
Python NaN is stored as NULL, so one poisoned holding raises IntegrityError
and rolls back every sibling row in the same call. Missing equity (leftover)
writes $0 instead — pin the NaN crash so the two stay distinct.
"""

from __future__ import annotations

import sqlite3

import pytest

from gesh_core import db


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "gesh_financial.db")
    db.init_db()
    yield


def test_nan_equity_raises_and_does_not_persist_siblings() -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.log_equity_snapshot(
            [
                {"symbol": "OK", "equity": 100.0, "current_price": 12.5},
                {"symbol": "BAD", "equity": float("nan"), "current_price": 10.0},
            ]
        )

    assert db.get_equity_history("OK") == []
    assert db.get_equity_history("BAD") == []
