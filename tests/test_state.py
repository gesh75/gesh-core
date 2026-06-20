"""Parity tests for gesh_core.trading.state (Phase 3.4).

Pins the execution-layer persistence both repos share: the intent→decision→order
audit chain, the order-rate counter, job markers (rule #38), and the
safety-critical two-book paper_realized_pnl_usd_today (rules #36/#40) that drives
the PAPER daily-loss circuit breaker.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    # Isolate every test to its own DB (never touch a real gesh_financial.db).
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def _today_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d") + "T12:00:00+00:00"


def test_module_loads_from_gesh_core():
    assert "gesh_core" in (state.__file__ or "")


# ─── resolver ─────────────────────────────────────────────────────────────────

def test_resolver_env_then_cwd(tmp_path, monkeypatch):
    target = tmp_path / "explicit.db"
    monkeypatch.setenv("GESH_DB_PATH", str(target))
    assert state._resolve_db() == target
    monkeypatch.delenv("GESH_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    assert state._resolve_db() == tmp_path / "gesh_financial.db"


# ─── audit chain ──────────────────────────────────────────────────────────────

def test_intent_decision_order_chain():
    state.init_trading_tables()
    iid = state.log_intent({"symbol": "NVDA", "action": "BUY", "confidence": 0.9,
                            "target_position_pct": 0.02, "source": "consensus"})
    assert iid > 0
    did = state.log_decision(iid, "APPROVED", None, {"KILL_SWITCH": True}, {"paper_mode": True})
    assert did > 0
    oid = state.log_order(iid, did, "paper", "coid-1", "SIMULATED", "NVDA", "BUY",
                          qty=10, target_price=100.0)
    assert oid > 0
    assert state.recent_orders()[0]["client_order_id"] == "coid-1"
    assert state.recent_intents()[0]["symbol"] == "NVDA"


def test_client_order_id_idempotency():
    state.init_trading_tables()
    iid = state.log_intent({"symbol": "X", "action": "BUY", "confidence": 1.0, "source": "m"})
    state.log_order(iid, None, "paper", "dup", "SIMULATED", "X", "BUY", 1, 1.0)
    with pytest.raises(sqlite3.IntegrityError):
        state.log_order(iid, None, "paper", "dup", "SIMULATED", "X", "BUY", 1, 1.0)


# ─── count_orders_today (approved_only superset) ──────────────────────────────

def test_count_orders_excludes_rejected_by_default():
    state.init_trading_tables()
    iid = state.log_intent({"symbol": "X", "action": "BUY", "confidence": 1.0, "source": "m"})
    state.log_order(iid, None, "paper", "ok1", "SIMULATED", "X", "BUY", 1, 1.0)
    state.log_order(iid, None, "paper", "rej1", "REJECTED", "X", "BUY", 1, 1.0)
    assert state.count_orders_today() == 1                      # rejected excluded
    assert state.count_orders_today(approved_only=False) == 2   # engine superset param
    assert state.count_orders_today(mode="paper") == 1


# ─── job markers (rule #38) ───────────────────────────────────────────────────

def test_job_markers_roundtrip():
    state.init_trading_tables()
    assert state.get_marker("entry_cycle_date") is None
    state.set_marker("entry_cycle_date", "2026-06-20")
    assert state.get_marker("entry_cycle_date") == "2026-06-20"
    state.set_marker("entry_cycle_date", "2026-06-21")          # upsert
    assert state.get_marker("entry_cycle_date") == "2026-06-21"


# ─── safety-critical: two-book paper realized P&L (rules #36/#40) ──────────────

def test_paper_realized_pnl_sums_both_books():
    state.init_trading_tables()
    today = _today_iso()
    today_date = today[:10]
    with state._conn() as con:
        con.execute("CREATE TABLE paper_outcomes (pnl_usd REAL, exit_at TEXT)")
        con.execute("INSERT INTO paper_outcomes VALUES (?, ?)", (-120.0, today))
        con.execute("CREATE TABLE paper_trades (realized_pnl REAL, exit_time TEXT)")
        con.execute("INSERT INTO paper_trades VALUES (?, ?)", (-30.0, today_date + " 10:00"))
    # -120 (tracker book) + -30 (daily-chain book) = -150
    assert state.paper_realized_pnl_usd_today() == pytest.approx(-150.0)


def test_paper_realized_pnl_engine_like_when_no_paper_trades():
    # Engine: paper_trades empty/absent -> equals paper_outcomes-only sum.
    state.init_trading_tables()
    with state._conn() as con:
        con.execute("CREATE TABLE paper_outcomes (pnl_usd REAL, exit_at TEXT)")
        con.execute("INSERT INTO paper_outcomes VALUES (?, ?)", (-75.0, _today_iso()))
    assert state.paper_realized_pnl_usd_today() == pytest.approx(-75.0)


def test_paper_realized_pnl_failsafe_no_tables():
    state.init_trading_tables()   # neither paper book exists
    assert state.paper_realized_pnl_usd_today() == 0.0


def test_paper_realized_pnl_ignores_other_days():
    state.init_trading_tables()
    with state._conn() as con:
        con.execute("CREATE TABLE paper_outcomes (pnl_usd REAL, exit_at TEXT)")
        con.execute("INSERT INTO paper_outcomes VALUES (?, ?)", (-999.0, "2020-01-01T00:00:00+00:00"))
    assert state.paper_realized_pnl_usd_today() == 0.0
