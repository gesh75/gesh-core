"""
trading/state.py — persistence for the execution layer.

Adds three tables to the SAME sqlite file used by db.py (gesh_financial.db):

  trade_intents  : every signal-layer output that became a TradeIntent
  risk_decisions : every gate verdict (approved or rejected, with reason)
  orders         : every simulated or real broker submission

A single intent_id chains signal → gate → order for end-to-end audit.

We intentionally do NOT import db.py to avoid circular imports when the
server boots. We do point at the same DB_PATH so every row lives together.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


# DB resolution (gesh-core can't use __file__ — it points inside the package, not
# either consumer repo). Each repo keeps its OWN gesh_financial.db (rule #44: the
# engine and product paper books are deliberately SEPARATE), so the default is
# cwd-relative — both servers/autopilot/chain run from their own repo root. Override
# explicitly via GESH_DB_PATH.
#
# VirtioFS (macOS shared mount) can't do SQLite DDL/WAL from a sandbox — probe the
# primary and fall back to /tmp/gesh_trading_state.db if it isn't writable. (Union of
# the product repo's _resolve_db fallback + the engine's create-if-missing behavior.)
def _resolve_db() -> Path:
    primary = Path(os.getenv("GESH_DB_PATH") or (Path.cwd() / "gesh_financial.db"))
    try:
        primary.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(primary))
        con.execute("CREATE TABLE IF NOT EXISTS _state_probe (id INTEGER)")
        con.execute("DROP TABLE IF EXISTS _state_probe")
        con.close()
        return primary
    except sqlite3.OperationalError:
        return Path("/tmp/gesh_trading_state.db")


DB_PATH = _resolve_db()


_DDL = """
CREATE TABLE IF NOT EXISTS trade_intents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT    NOT NULL,
    symbol          TEXT    NOT NULL,
    action          TEXT    NOT NULL,        -- BUY | SELL | HOLD
    confidence      REAL    NOT NULL,
    target_pct      REAL,                    -- desired position as % of equity (0..1)
    stop_loss       REAL,
    take_profit     REAL,
    time_in_force   TEXT,                    -- day | gtc | ioc | fok
    source          TEXT    NOT NULL,        -- which engine produced this (consensus, kelly, manual, ...)
    schema_version  INTEGER NOT NULL DEFAULT 1,
    raw_json        TEXT                     -- full intent as JSON
);

CREATE TABLE IF NOT EXISTS risk_decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    decided_at      TEXT    NOT NULL,
    intent_id       INTEGER NOT NULL,
    verdict         TEXT    NOT NULL,        -- APPROVED | REJECTED
    reason          TEXT,                    -- human-readable rejection reason
    gates_json      TEXT,                    -- per-gate pass/fail map
    config_json     TEXT,                    -- snapshot of RiskConfig at decision time
    FOREIGN KEY (intent_id) REFERENCES trade_intents(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    placed_at       TEXT    NOT NULL,
    intent_id       INTEGER NOT NULL,
    decision_id     INTEGER,
    mode            TEXT    NOT NULL,        -- paper | live | backtest
    client_order_id TEXT    UNIQUE NOT NULL, -- idempotency key
    broker_order_id TEXT,
    status          TEXT    NOT NULL,        -- SIMULATED | SUBMITTED | FILLED | REJECTED | ERROR
    symbol          TEXT    NOT NULL,
    action          TEXT    NOT NULL,
    qty             REAL,
    target_price    REAL,
    fill_price      REAL,
    fill_qty        REAL,
    error           TEXT,
    response_json   TEXT,
    FOREIGN KEY (intent_id)   REFERENCES trade_intents(id),
    FOREIGN KEY (decision_id) REFERENCES risk_decisions(id)
);

CREATE INDEX IF NOT EXISTS idx_intents_created ON trade_intents(created_at);
CREATE INDEX IF NOT EXISTS idx_intents_symbol  ON trade_intents(symbol, created_at);
CREATE INDEX IF NOT EXISTS idx_decisions_intent ON risk_decisions(intent_id);
CREATE INDEX IF NOT EXISTS idx_orders_intent   ON orders(intent_id);
CREATE INDEX IF NOT EXISTS idx_orders_placed   ON orders(placed_at);
CREATE INDEX IF NOT EXISTS idx_orders_mode     ON orders(mode, placed_at);

CREATE TABLE IF NOT EXISTS job_markers (
    name        TEXT PRIMARY KEY,           -- e.g. 'entry_cycle_date'
    value       TEXT NOT NULL,              -- e.g. '2026-06-08'
    updated_at  TEXT NOT NULL
);
"""


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    # WAL + busy_timeout: concurrent writers (autopilot, daily chain, sessions)
    # otherwise hit "database is locked" under contention.
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    try:
        con.executescript(_DDL)
        yield con
        con.commit()
    finally:
        con.close()


def init_trading_tables() -> None:
    """Ensure the three trading tables exist. Safe to call repeatedly."""
    with _conn():
        pass


def get_marker(name: str) -> str | None:
    """Read a persistent job marker (e.g. the date the entry cycle last ran).

    Backed by the job_markers table (created by _DDL on every connection), so no
    fail-safe is needed. Returns None when the marker has never been set.
    """
    with _conn() as con:
        row = con.execute(
            "SELECT value FROM job_markers WHERE name = ?", [name]
        ).fetchone()
    return row["value"] if row else None


def set_marker(name: str, value: str) -> None:
    """Upsert a persistent job marker.

    Survives autopilot restarts so catch_up_on_wake() can tell whether today's
    entry cycle already ran — preventing a duplicate daily Robinhood credential
    login after a restart.
    """
    now = datetime.now(UTC).isoformat()
    with _conn() as con:
        con.execute(
            "INSERT INTO job_markers(name, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            [name, value, now],
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ─── trade_intents ────────────────────────────────────────────────────────────

def log_intent(intent: dict[str, Any]) -> int:
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO trade_intents
              (created_at, symbol, action, confidence, target_pct,
               stop_loss, take_profit, time_in_force, source, schema_version, raw_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                intent.get("generated_at", _now()),
                intent["symbol"],
                intent["action"],
                float(intent.get("confidence", 0.0)),
                intent.get("target_position_pct"),
                intent.get("stop_loss"),
                intent.get("take_profit"),
                intent.get("time_in_force", "day"),
                intent.get("source", "unknown"),
                int(intent.get("schema_version", 1)),
                json.dumps(intent, default=str),
            ),
        )
        return cur.lastrowid


# ─── risk_decisions ───────────────────────────────────────────────────────────

def log_decision(
    intent_id: int,
    verdict: str,
    reason: str | None,
    gates: dict[str, bool],
    config_snapshot: dict[str, Any],
) -> int:
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO risk_decisions
              (decided_at, intent_id, verdict, reason, gates_json, config_json)
            VALUES (?,?,?,?,?,?)
            """,
            (_now(), intent_id, verdict, reason,
             json.dumps(gates), json.dumps(config_snapshot, default=str)),
        )
        return cur.lastrowid


# ─── orders ───────────────────────────────────────────────────────────────────

def log_order(
    intent_id: int,
    decision_id: int | None,
    mode: str,
    client_order_id: str,
    status: str,
    symbol: str,
    action: str,
    qty: float | None,
    target_price: float | None,
    broker_order_id: str | None = None,
    fill_price: float | None = None,
    fill_qty: float | None = None,
    error: str | None = None,
    response: dict[str, Any] | None = None,
) -> int:
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO orders
              (placed_at, intent_id, decision_id, mode, client_order_id, broker_order_id,
               status, symbol, action, qty, target_price, fill_price, fill_qty,
               error, response_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (_now(), intent_id, decision_id, mode, client_order_id, broker_order_id,
             status, symbol, action, qty, target_price, fill_price, fill_qty,
             error, json.dumps(response, default=str) if response else None),
        )
        return cur.lastrowid


# ─── counters / history ───────────────────────────────────────────────────────

def count_orders_today(mode: str | None = None, approved_only: bool = True) -> int:
    """Orders submitted since 00:00 UTC today.

    Args:
        mode: Pass mode='paper' to filter to paper orders only.
        approved_only: When True (default), only count non-REJECTED orders toward
            the daily cap. Rejected orders don't consume the rate limit — only
            actual fills (SIMULATED, APPROVED, FILLED) count. This prevents the
            midday rebalance from burning all 3 slots with rejected intents before
            any real signal gets through.
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    sql = "SELECT COUNT(*) AS n FROM orders WHERE placed_at >= ?"
    params: list[Any] = [today + "T00:00:00+00:00"]
    if approved_only:
        sql += " AND status != 'REJECTED'"
    if mode:
        sql += " AND mode = ?"
        params.append(mode)
    with _conn() as con:
        return int(con.execute(sql, params).fetchone()["n"])


def paper_realized_pnl_usd_today() -> float:
    """Sum of realized P&L from the paper book closed since 00:00 UTC today.

    Drives the PAPER-mode daily-loss circuit breaker (rules #36/#40) — the paper
    book's OWN realized loss today, NOT the real Robinhood account's intraday swing.
    Checks BOTH possible paper books in this DB and sums them:
      - paper_outcomes (tracker convention — the engine's autonomy-gate book)
      - trade_log's paper_trades (the product daily-analysis paper sessions)
    Each is owned elsewhere (not this module's _DDL), so a missing table fails safe
    to 0.0. In the engine, paper_trades is empty/legacy (rule #20) so this equals the
    paper_outcomes-only sum; in the product, both contribute. A flat paper day never
    blocks entries.
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    total = 0.0
    with _conn() as con:
        try:
            row = con.execute(
                "SELECT COALESCE(SUM(pnl_usd), 0.0) AS s FROM paper_outcomes WHERE exit_at >= ?",
                [today + "T00:00:00+00:00"],
            ).fetchone()
            total += float(row["s"] or 0.0)
        except sqlite3.OperationalError:
            pass
        try:
            row = con.execute(
                "SELECT COALESCE(SUM(realized_pnl), 0.0) AS s FROM paper_trades "
                "WHERE exit_time IS NOT NULL AND substr(exit_time, 1, 10) = ?",
                [today],
            ).fetchone()
            total += float(row["s"] or 0.0)
        except sqlite3.OperationalError:
            pass
    return total


def recent_orders(limit: int = 25) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def recent_intents(limit: int = 25) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM trade_intents ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
