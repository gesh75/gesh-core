"""A valid-price holding missing ``symbol`` aborts the snapshot write.

Invalid prices are filtered with a warning. A remaining row still requires
``h["symbol"]`` at insert — ``KeyError`` before any persist. A mixed book
therefore drops the good rows too (transaction rollback). Pin the crash so
a later per-row skip cannot silently start writing a partial ECG history.
"""

from __future__ import annotations

import pytest

from gesh_core import db


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "gesh_financial.db")
    db.init_db()
    yield


def test_missing_symbol_on_valid_price_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        db.log_equity_snapshot([{"current_price": 10.0, "equity": 100}])


def test_mixed_book_raises_and_writes_nothing() -> None:
    with pytest.raises(KeyError):
        db.log_equity_snapshot(
            [
                {"symbol": "NVDA", "current_price": 100.0, "equity": 1_000},
                {"current_price": 10.0, "equity": 100},
            ]
        )
    assert db.get_equity_history("NVDA") == []
    assert db.get_all_latest_snapshots() == []


def test_all_invalid_prices_without_symbol_do_not_raise(capsys) -> None:
    # Contrast: filtered out before the insert subscript.
    db.log_equity_snapshot([{"current_price": 0, "equity": 100}])
    assert db.get_all_latest_snapshots() == []
    assert "invalid price" in capsys.readouterr().out
