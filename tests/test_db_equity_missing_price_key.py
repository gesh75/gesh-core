"""A holding with no current_price is treated as 0 and skipped.

``holding.get("current_price") or 0`` plus the non-positive guard must
not persist a $0 ECG row. Sibling valid holdings in the same snapshot
must still write.
"""
from __future__ import annotations

from gesh_core import db


def test_missing_current_price_key_is_skipped_without_losing_valid_rows(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "gesh_financial.db")
    db.init_db()
    db.log_equity_snapshot(
        [
            {"symbol": "VALID", "equity": 100, "current_price": 12.5},
            {"symbol": "NOPRICE", "equity": 200},
            {"symbol": "NONEPRICE", "equity": 300, "current_price": None},
        ]
    )

    assert db.get_equity_history("VALID")[0]["current_price"] == 12.5
    assert db.get_equity_history("NOPRICE") == []
    assert db.get_equity_history("NONEPRICE") == []
    warning = capsys.readouterr().out
    assert "NOPRICE" in warning
    assert "NONEPRICE" in warning
