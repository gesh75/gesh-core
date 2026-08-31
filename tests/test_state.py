"""Parity tests for gesh_core.trading.state (Phase 3.4).

Pins the execution-layer persistence both repos share: the intent→decision→order
audit chain, the order-rate counter, job markers (rule #38), and the
safety-critical two-book paper_realized_pnl_usd_today (rules #36/#40) that drives
the PAPER daily-loss circuit breaker.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    # Isolate every test to its own DB (never touch a real gesh_financial.db).
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def _insert_order(
    *,
    placed_at: str,
    client_order_id: str,
    status: str = "SIMULATED",
    action: str = "BUY",
    qty: float | None = 1.0,
    fill_qty: float | None = None,
    mode: str = "paper",
) -> None:
    state.init_trading_tables()
    with state._conn() as con:
        con.execute(
            """
            INSERT INTO orders
              (placed_at, intent_id, mode, client_order_id, status, symbol,
               action, qty, fill_qty)
            VALUES (?, 1, ?, ?, ?, 'TEST', ?, ?, ?)
            """,
            (placed_at, mode, client_order_id, status, action, qty, fill_qty),
        )


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
    iid = state.log_intent(
        {
            "symbol": "NVDA",
            "action": "BUY",
            "confidence": 0.9,
            "target_position_pct": 0.02,
            "source": "consensus",
        }
    )
    assert iid > 0
    did = state.log_decision(iid, "APPROVED", None, {"KILL_SWITCH": True}, {"paper_mode": True})
    assert did > 0
    oid = state.log_order(
        iid, did, "paper", "coid-1", "SIMULATED", "NVDA", "BUY", qty=10, target_price=100.0
    )
    assert oid > 0
    assert state.recent_orders()[0]["client_order_id"] == "coid-1"
    assert state.recent_intents()[0]["symbol"] == "NVDA"


def test_client_order_id_idempotency():
    state.init_trading_tables()
    iid = state.log_intent({"symbol": "X", "action": "BUY", "confidence": 1.0, "source": "m"})
    state.log_order(iid, None, "paper", "dup", "SIMULATED", "X", "BUY", 1, 1.0)
    with pytest.raises(sqlite3.IntegrityError):
        state.log_order(iid, None, "paper", "dup", "SIMULATED", "X", "BUY", 1, 1.0)


PROVENANCE_COLUMNS = {
    "purpose",
    "canonical_key",
    "run_id",
    "strategy_version",
    "quote_provider",
    "quote_as_of",
}


def test_legacy_trade_intents_table_gains_provenance_columns_idempotently():
    with sqlite3.connect(state.DB_PATH) as con:
        con.execute(
            """
            CREATE TABLE trade_intents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence REAL NOT NULL,
                target_pct REAL,
                stop_loss REAL,
                take_profit REAL,
                time_in_force TEXT,
                source TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 1,
                raw_json TEXT
            )
            """
        )
        con.execute(
            """
            INSERT INTO trade_intents
              (created_at, symbol, action, confidence, source)
            VALUES ('2026-08-01T00:00:00+00:00', 'LEGACY', 'HOLD', 0.5, 'legacy')
            """
        )

    state.init_trading_tables()
    state.init_trading_tables()

    with sqlite3.connect(state.DB_PATH) as con:
        columns = {row[1] for row in con.execute("PRAGMA table_info(trade_intents)").fetchall()}
        legacy = con.execute(
            "SELECT symbol, purpose, canonical_key, run_id FROM trade_intents"
        ).fetchone()
        indexes = {row[1] for row in con.execute("PRAGMA index_list(trade_intents)").fetchall()}
    assert PROVENANCE_COLUMNS <= columns
    assert legacy == ("LEGACY", None, None, None)
    assert {
        "idx_intents_canonical_key",
        "idx_intents_run_id",
        "idx_intents_qualification",
    } <= indexes


def test_log_and_read_intent_by_canonical_key_persists_all_provenance():
    provenance = {
        "purpose": "ENTRY",
        "canonical_key": "run-42:NVDA:BUY",
        "run_id": "run-42",
        "strategy_version": "strategy-v3",
        "quote_provider": "fixture-provider",
        "quote_as_of": "2026-08-04T12:34:56+00:00",
    }
    intent = {
        "symbol": "NVDA",
        "action": "BUY",
        "confidence": 0.9,
        "target_position_pct": 0.02,
        "source": "consensus",
        **provenance,
    }

    intent_id = state.log_intent(intent)
    stored = state.get_intent_by_canonical_key(provenance["canonical_key"])

    assert stored is not None
    assert stored["id"] == intent_id
    assert {key: stored[key] for key in provenance} == provenance


def test_read_intent_by_canonical_key_supports_standard_caller_connection():
    canonical_key = "run-42:X:HOLD"
    state.log_intent(
        {
            "symbol": "X",
            "action": "HOLD",
            "confidence": 0.5,
            "source": "test",
            "canonical_key": canonical_key,
        }
    )

    with sqlite3.connect(state.DB_PATH) as con:
        stored = state.get_intent_by_canonical_key(
            canonical_key,
            connection=con,
        )

    assert stored is not None
    assert stored["canonical_key"] == canonical_key
    assert stored["symbol"] == "X"


def test_null_canonical_keys_coexist_but_duplicate_non_null_key_fails():
    legacy = {"symbol": "X", "action": "HOLD", "confidence": 0.5, "source": "legacy"}
    assert state.log_intent(legacy) > 0
    assert state.log_intent(legacy) > 0

    canonical = {
        **legacy,
        "canonical_key": "run-42:X:HOLD",
    }
    assert state.log_intent(canonical) > 0
    with pytest.raises(sqlite3.IntegrityError):
        state.log_intent(canonical)


# ─── count_orders_today (approved_only superset) ──────────────────────────────


def test_count_orders_excludes_rejected_by_default():
    state.init_trading_tables()
    iid = state.log_intent({"symbol": "X", "action": "BUY", "confidence": 1.0, "source": "m"})
    state.log_order(iid, None, "paper", "ok1", "SIMULATED", "X", "BUY", 1, 1.0)
    state.log_order(iid, None, "paper", "rej1", "REJECTED", "X", "BUY", 1, 1.0)
    assert state.count_orders_today() == 1  # rejected excluded
    assert state.count_orders_today(approved_only=False) == 2  # engine superset param
    assert state.count_orders_today(mode="paper") == 1


def test_count_orders_today_uses_et_dst_midnight_bounds():
    # 2026-03-08 is a 23-hour ET day: [05:00Z, next-day 04:00Z).
    now = datetime(2026, 3, 8, 12, tzinfo=ZoneInfo("America/New_York"))
    _insert_order(placed_at="2026-03-08T04:59:59+00:00", client_order_id="before")
    _insert_order(placed_at="2026-03-08T05:00:00+00:00", client_order_id="lower")
    _insert_order(placed_at="2026-03-09T03:59:59+00:00", client_order_id="inside")
    _insert_order(placed_at="2026-03-09T04:00:00+00:00", client_order_id="upper")

    assert state.count_orders_today(now=now) == 2


def test_count_orders_today_counts_only_actionable_positive_orders():
    now = datetime(2026, 8, 4, 12, tzinfo=ZoneInfo("America/New_York"))
    placed_at = "2026-08-04T16:00:00+00:00"
    rows = [
        ("sim-buy", "SIMULATED", "BUY", 1.0, None),
        ("submitted-sell", "SUBMITTED", "SELL", 2.0, None),
        ("filled-buy", "FILLED", "BUY", None, 3.0),
        ("hold", "SIMULATED", "HOLD", 1.0, 1.0),
        ("skipped", "SKIPPED", "BUY", 1.0, 1.0),
        ("rejected", "REJECTED", "BUY", 1.0, 1.0),
        ("error", "ERROR", "SELL", 1.0, 1.0),
        ("zero", "SIMULATED", "BUY", 0.0, 0.0),
        ("null", "SUBMITTED", "SELL", None, None),
        ("negative", "FILLED", "BUY", -1.0, -1.0),
    ]
    for client_order_id, status, action, qty, fill_qty in rows:
        _insert_order(
            placed_at=placed_at,
            client_order_id=client_order_id,
            status=status,
            action=action,
            qty=qty,
            fill_qty=fill_qty,
        )

    assert state.count_orders_today(now=now) == 4


def test_count_orders_today_preserves_mode_filter():
    now = datetime(2026, 8, 4, 12, tzinfo=ZoneInfo("America/New_York"))
    placed_at = "2026-08-04T16:00:00+00:00"
    _insert_order(placed_at=placed_at, client_order_id="paper", mode="paper")
    _insert_order(placed_at=placed_at, client_order_id="live", mode="live")

    assert state.count_orders_today(now=now) == 2
    assert state.count_orders_today(mode="paper", now=now) == 1
    assert state.count_orders_today(mode="live", now=now) == 1


def test_count_orders_today_unapproved_mode_retains_all_audit_rows_inside_et_day():
    now = datetime(2026, 8, 4, 12, tzinfo=ZoneInfo("America/New_York"))
    inside = "2026-08-04T16:00:00+00:00"
    _insert_order(
        placed_at=inside,
        client_order_id="hold",
        status="SIMULATED",
        action="HOLD",
        qty=0.0,
    )
    _insert_order(
        placed_at=inside,
        client_order_id="skipped",
        status="SKIPPED",
        qty=0.0,
    )
    _insert_order(placed_at=inside, client_order_id="rejected", status="REJECTED")
    _insert_order(placed_at=inside, client_order_id="error", status="ERROR", mode="live")
    _insert_order(
        placed_at="2026-08-05T04:00:00+00:00",
        client_order_id="next-day",
        status="ERROR",
    )

    assert state.count_orders_today(approved_only=False, now=now) == 4
    assert state.count_orders_today(mode="paper", approved_only=False, now=now) == 3


# ─── job markers (rule #38) ───────────────────────────────────────────────────


def test_job_markers_roundtrip():
    state.init_trading_tables()
    assert state.get_marker("entry_cycle_date") is None
    state.set_marker("entry_cycle_date", "2026-06-20")
    assert state.get_marker("entry_cycle_date") == "2026-06-20"
    state.set_marker("entry_cycle_date", "2026-06-21")  # upsert
    assert state.get_marker("entry_cycle_date") == "2026-06-21"


# ─── safety-critical: two-book paper realized P&L (rules #36/#40) ──────────────


def test_paper_realized_pnl_sums_both_books():
    state.init_trading_tables()
    now = datetime(2026, 8, 4, 16, tzinfo=ZoneInfo("America/New_York"))
    with state._conn() as con:
        con.execute("CREATE TABLE paper_outcomes (pnl_usd REAL, exit_at TEXT)")
        con.execute(
            "INSERT INTO paper_outcomes VALUES (?, ?)",
            (-120.0, "2026-08-04T16:00:00+00:00"),
        )
        con.execute("CREATE TABLE paper_trades (realized_pnl REAL, exit_time TEXT)")
        con.execute("INSERT INTO paper_trades VALUES (?, ?)", (-30.0, "2026-08-04 10:00"))
    # -120 (tracker book) + -30 (daily-chain book) = -150
    assert state.paper_realized_pnl_usd_today(now=now) == pytest.approx(-150.0)


def test_paper_realized_pnl_engine_like_when_no_paper_trades():
    # Engine: paper_trades empty/absent -> equals paper_outcomes-only sum.
    state.init_trading_tables()
    now = datetime(2026, 8, 4, 16, tzinfo=ZoneInfo("America/New_York"))
    with state._conn() as con:
        con.execute("CREATE TABLE paper_outcomes (pnl_usd REAL, exit_at TEXT)")
        con.execute(
            "INSERT INTO paper_outcomes VALUES (?, ?)",
            (-75.0, "2026-08-04T16:00:00+00:00"),
        )
    assert state.paper_realized_pnl_usd_today(now=now) == pytest.approx(-75.0)


def test_paper_realized_pnl_failsafe_no_tables():
    state.init_trading_tables()  # neither paper book exists
    assert state.paper_realized_pnl_usd_today() == 0.0


def test_paper_realized_pnl_ignores_other_days():
    state.init_trading_tables()
    now = datetime(2026, 8, 4, 16, tzinfo=ZoneInfo("America/New_York"))
    with state._conn() as con:
        con.execute("CREATE TABLE paper_outcomes (pnl_usd REAL, exit_at TEXT)")
        con.execute(
            "INSERT INTO paper_outcomes VALUES (?, ?)", (-999.0, "2020-01-01T00:00:00+00:00")
        )
    assert state.paper_realized_pnl_usd_today(now=now) == 0.0


def test_paper_realized_pnl_keeps_same_et_day_losses_after_utc_midnight():
    """Afternoon ET losses must still trip the breaker after 20:00 ET.

    UTC midnight is 20:00 EDT / 19:00 EST. A UTC-day window dropped those
    closes and the daily-loss gate failed open for the rest of the ET session.
    """
    state.init_trading_tables()
    with state._conn() as con:
        con.execute("CREATE TABLE paper_outcomes (pnl_usd REAL, exit_at TEXT)")
        con.execute(
            "INSERT INTO paper_outcomes VALUES (?, ?)",
            (-1000.0, "2026-08-04T19:00:00+00:00"),  # 15:00 EDT
        )
        con.execute("CREATE TABLE paper_trades (realized_pnl REAL, exit_time TEXT)")
        con.execute("INSERT INTO paper_trades VALUES (?, ?)", (-250.0, "2026-08-04 15:00"))

    evening = datetime(2026, 8, 4, 21, tzinfo=ZoneInfo("America/New_York"))
    assert state.paper_realized_pnl_usd_today(now=evening) == pytest.approx(-1250.0)

    next_morning = datetime(2026, 8, 5, 9, tzinfo=ZoneInfo("America/New_York"))
    assert state.paper_realized_pnl_usd_today(now=next_morning) == 0.0


def test_paper_realized_pnl_uses_et_dst_midnight_bounds():
    # 2026-03-08 is a 23-hour ET day: [05:00Z, next-day 04:00Z).
    state.init_trading_tables()
    now = datetime(2026, 3, 8, 21, tzinfo=ZoneInfo("America/New_York"))
    with state._conn() as con:
        con.execute("CREATE TABLE paper_outcomes (pnl_usd REAL, exit_at TEXT)")
        con.executemany(
            "INSERT INTO paper_outcomes VALUES (?, ?)",
            [
                (-10.0, "2026-03-08T04:59:59+00:00"),  # previous ET day
                (-20.0, "2026-03-08T05:00:00+00:00"),  # ET midnight
                (-40.0, "2026-03-09T03:59:59+00:00"),  # still 2026-03-08 ET
                (-80.0, "2026-03-09T04:00:00+00:00"),  # next ET day
            ],
        )

    assert state.paper_realized_pnl_usd_today(now=now) == pytest.approx(-60.0)


def test_paper_realized_pnl_rejects_naive_now():
    with pytest.raises(ValueError, match="timezone-aware"):
        state.paper_realized_pnl_usd_today(now=datetime(2026, 8, 4, 16))


def test_count_orders_includes_error_by_default():
    # Broker/network ERROR rows consume the cap because the failure may have
    # occurred after the broker accepted the order.
    state.init_trading_tables()
    iid = state.log_intent({"symbol": "X", "action": "BUY", "confidence": 1.0, "source": "m"})
    state.log_order(iid, None, "live", "ok-e1", "SUBMITTED", "X", "BUY", 1, 1.0)
    state.log_order(iid, None, "live", "err-e1", "ERROR", "X", "BUY", 1, 1.0, error="timeout")
    state.log_order(iid, None, "live", "rej-e1", "REJECTED", "X", "BUY", 1, 1.0)
    assert state.count_orders_today(mode="live") == 2  # SUBMITTED + ERROR; REJECTED excluded
    assert state.count_orders_today(approved_only=False) == 3  # superset still sees all
