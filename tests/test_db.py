"""Parity tests for gesh_core.db (Phase 3.6).

Pins the union both repos share: the WAL connect() helper (engine), the
corruption-tolerant _safe_json/get_analysis_by_id + get_portfolio_equity_history
(product), and the analysis/equity round-trips. DB resolves to a tmp file via
monkeypatched DB_PATH so the real gesh_financial.db is never touched.
"""
from __future__ import annotations

import pytest

from gesh_core import db


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "gesh_financial.db")
    db.init_db()
    yield


def test_module_loads_from_gesh_core():
    assert "gesh_core" in (db.__file__ or "")


# ─── resolver ─────────────────────────────────────────────────────────────────

def test_resolver_env_or_cwd(tmp_path, monkeypatch):
    # DB_PATH is computed at import; just assert the resolver inputs behave.
    monkeypatch.setenv("GESH_DB_PATH", str(tmp_path / "x.db"))
    import importlib
    importlib.reload(db)
    try:
        assert db.DB_PATH == tmp_path / "x.db"
    finally:
        monkeypatch.delenv("GESH_DB_PATH", raising=False)
        importlib.reload(db)


# ─── connect() WAL helper (engine) ────────────────────────────────────────────

def test_connect_enables_wal(tmp_path):
    con = db.connect(str(tmp_path / "w.db"))
    try:
        mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        con.close()


# ─── analysis round-trip + corruption tolerance (product) ─────────────────────

def test_log_and_get_analysis():
    rid = db.log_analysis("sonnet", {"in": 1}, {"portfolio_score": 80, "risk_score": 30})
    row = db.get_analysis_by_id(rid)
    assert row["payload"] == {"in": 1}
    assert row["result"]["portfolio_score"] == 80
    assert "parse_error" not in row
    hist = db.get_analysis_history()
    assert hist[0]["id"] == rid and hist[0]["portfolio_score"] == 80


def test_safe_json_tolerates_corruption():
    assert db._safe_json(None) == ({}, False)
    assert db._safe_json("") == ({}, False)
    assert db._safe_json('{"a": 1}') == ({"a": 1}, False)
    assert db._safe_json("not json{{") == ({}, True)
    assert db._safe_json("[1,2,3]") == ({}, False)   # non-dict JSON -> empty dict, no error


def test_get_analysis_by_id_degrades_on_corrupt_row():
    rid = db.log_analysis("m", {"ok": 1}, {"ok": 2})
    # Corrupt the stored result_json directly.
    with db._conn() as con:
        con.execute("UPDATE analysis_runs SET result_json='broken{{' WHERE id=?", (rid,))
    row = db.get_analysis_by_id(rid)
    assert row["parse_error"] is True
    assert row["result"] == {}            # degraded, did not raise
    assert row["payload"] == {"ok": 1}


def test_get_analysis_by_id_missing_returns_none():
    assert db.get_analysis_by_id(999999) is None


# ─── equity snapshots + portfolio history (product) ───────────────────────────

def test_equity_snapshot_and_history():
    db.log_equity_snapshot([{"symbol": "NVDA", "equity": 1000, "percent_change": 2.0, "current_price": 100}])
    hist = db.get_equity_history("NVDA")
    assert hist[0]["equity"] == 1000
    latest = db.get_all_latest_snapshots()
    assert any(r["symbol"] == "NVDA" for r in latest)


def test_equity_snapshot_skips_invalid_prices_without_losing_valid_rows(capsys):
    db.log_equity_snapshot(
        [
            {"symbol": "VALID", "equity": 100, "current_price": "12.5"},
            {"symbol": "TEXT", "equity": 200, "current_price": "N/A"},
            {"symbol": "OBJECT", "equity": 300, "current_price": object()},
            {"symbol": "NAN", "equity": 400, "current_price": float("nan")},
            {"symbol": "INFINITY", "equity": 500, "current_price": float("inf")},
            {"symbol": "ZERO", "equity": 600, "current_price": 0},
        ]
    )

    assert db.get_equity_history("VALID")[0]["current_price"] == 12.5
    assert db.get_all_latest_snapshots() == [
        {
            "symbol": "VALID",
            "equity": 100.0,
            "percent_change": 0.0,
            "current_price": 12.5,
            "snapshot_at": db.get_equity_history("VALID")[0]["snapshot_at"],
        }
    ]
    warning = capsys.readouterr().out
    for symbol in ("TEXT", "OBJECT", "NAN", "INFINITY", "ZERO"):
        assert symbol in warning


def test_get_portfolio_equity_history_sums_and_orders():
    # two snapshots at different timestamps -> summed per timestamp, oldest->newest
    with db._conn() as con:
        con.execute("INSERT INTO equity_snapshots (snapshot_at, symbol, equity) VALUES ('2026-06-01T00:00:00','A',100)")
        con.execute("INSERT INTO equity_snapshots (snapshot_at, symbol, equity) VALUES ('2026-06-01T00:00:00','B',50)")
        con.execute("INSERT INTO equity_snapshots (snapshot_at, symbol, equity) VALUES ('2026-06-02T00:00:00','A',200)")
    series = db.get_portfolio_equity_history(points=10)
    assert series[0]["snapshot_at"] == "2026-06-01T00:00:00"   # oldest first
    assert series[0]["total_equity"] == 150                    # 100 + 50
    assert series[-1]["total_equity"] == 200


@pytest.mark.parametrize(
    ("accessor", "argument"),
    [
        (db.get_analysis_history, "limit"),
        (lambda **kw: db.get_equity_history("NVDA", **kw), "days"),
        (db.get_portfolio_equity_history, "points"),
    ],
)
def test_history_limits_reject_invalid_values(accessor, argument):
    for value in (0, -1):
        with pytest.raises(ValueError, match="must be positive"):
            accessor(**{argument: value})
    for value in (True, 1.5, "10", None):
        with pytest.raises(TypeError, match="must be an integer"):
            accessor(**{argument: value})


@pytest.mark.parametrize(
    ("accessor", "argument", "maximum"),
    [
        (db.get_analysis_history, "limit", db._MAX_ANALYSIS_HISTORY),
        (
            lambda **kw: db.get_equity_history("NVDA", **kw),
            "days",
            db._MAX_EQUITY_HISTORY,
        ),
        (
            db.get_portfolio_equity_history,
            "points",
            db._MAX_PORTFOLIO_EQUITY_HISTORY,
        ),
    ],
)
def test_history_limits_are_clamped(monkeypatch, accessor, argument, maximum):
    seen = []
    original = db._bounded_limit

    def capture(value, *, name, maximum):
        result = original(value, name=name, maximum=maximum)
        seen.append(result)
        return result

    monkeypatch.setattr(db, "_bounded_limit", capture)
    accessor(**{argument: 10**9})
    assert seen == [maximum]
