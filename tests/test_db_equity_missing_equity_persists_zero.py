"""Valid-price snapshots with missing equity persist $0, not a skip.

#72 pins a missing ``current_price`` key (row skipped). ``equity`` is
optional on the insert and defaults to 0. ECG then sees a crash to $0 and
can SUSPEND a holding that only omitted the field. Negative prices stay
refused so they cannot poison the same table.
"""

from __future__ import annotations

import pytest

from gesh_core import db


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "gesh_financial.db")
    db.init_db()
    yield


def test_missing_equity_key_persists_zero_when_price_is_valid() -> None:
    db.log_equity_snapshot([{"symbol": "NVDA", "current_price": 120.0}])
    hist = db.get_equity_history("NVDA")
    assert hist[0]["current_price"] == 120.0
    assert hist[0]["equity"] == 0


def test_negative_price_is_skipped_even_with_equity(capsys) -> None:
    db.log_equity_snapshot(
        [{"symbol": "NEG", "equity": 1_000.0, "current_price": -12.5}]
    )
    assert db.get_equity_history("NEG") == []
    assert "NEG" in capsys.readouterr().out
