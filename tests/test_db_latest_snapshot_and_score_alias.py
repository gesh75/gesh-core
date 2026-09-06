"""ECG / dashboard reads depend on latest-per-symbol snapshots and the
``diversification_score`` key name.

``get_all_latest_snapshots`` must pick MAX(snapshot_at) per symbol — an older
row winning would feed ECG a stale equity curve. ``log_analysis`` stores
``result["diversification_score"]`` into the ``diversification`` column; a
caller that only sets ``diversification`` silently persists NULL.
"""
from __future__ import annotations

import pytest

from gesh_core import db


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "gesh_financial.db")
    db.init_db()
    yield


def test_get_all_latest_snapshots_picks_newest_per_symbol():
    with db._conn() as con:
        con.execute(
            "INSERT INTO equity_snapshots (snapshot_at, symbol, equity, current_price) "
            "VALUES ('2026-06-01T00:00:00','NVDA',100,10)"
        )
        con.execute(
            "INSERT INTO equity_snapshots (snapshot_at, symbol, equity, current_price) "
            "VALUES ('2026-06-02T00:00:00','NVDA',250,12)"
        )
        con.execute(
            "INSERT INTO equity_snapshots (snapshot_at, symbol, equity, current_price) "
            "VALUES ('2026-06-02T00:00:00','AAPL',80,8)"
        )

    latest = {row["symbol"]: row for row in db.get_all_latest_snapshots()}
    assert set(latest) == {"NVDA", "AAPL"}
    assert latest["NVDA"]["equity"] == 250
    assert latest["NVDA"]["snapshot_at"] == "2026-06-02T00:00:00"
    assert latest["AAPL"]["equity"] == 80


def test_log_analysis_reads_diversification_score_not_diversification():
    rid = db.log_analysis(
        "sonnet",
        {"in": 1},
        {"portfolio_score": 80, "diversification_score": 77, "diversification": 1},
    )
    hist = db.get_analysis_history()
    assert hist[0]["id"] == rid
    assert hist[0]["diversification"] == 77


def test_log_analysis_wrong_key_persists_null_diversification():
    db.log_analysis("sonnet", {}, {"portfolio_score": 50, "diversification": 99})
    assert db.get_analysis_history()[0]["diversification"] is None
