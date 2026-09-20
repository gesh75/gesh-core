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
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

# DB resolution lives in gesh_core.db_path — shared with db.py so the audit chain
# and the paper books (which drive the daily-loss breaker) can never land in two
# different files. `_resolve_db` is kept as an alias for existing import sites.
from gesh_core.db_path import resolve_db_path as _resolve_db

DB_PATH = _resolve_db()


class LedgerUnavailable(RuntimeError):
    """Neither paper book is readable. This is not a measured $0 day."""


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

CREATE TABLE IF NOT EXISTS paper_stops (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at         TEXT    NOT NULL,
    order_row_id       INTEGER,             -- orders.id of the entry fill
    symbol             TEXT    NOT NULL,
    entry_price        REAL    NOT NULL,
    stop_price         REAL    NOT NULL,
    take_profit_price  REAL,
    volatility_tier    TEXT,
    active             INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_paper_stops_active ON paper_stops(active, symbol);
"""

_INTENT_PROVENANCE_COLUMNS = (
    ("purpose", "TEXT"),
    ("canonical_key", "TEXT"),
    ("run_id", "TEXT"),
    ("strategy_version", "TEXT"),
    ("quote_provider", "TEXT"),
    ("quote_as_of", "TEXT"),
)


def _migrate_trade_intent_provenance(con: sqlite3.Connection) -> None:
    """Add nullable provenance without relabeling any historical intent."""
    existing = {row["name"] for row in con.execute("PRAGMA table_info(trade_intents)").fetchall()}
    for column, column_type in _INTENT_PROVENANCE_COLUMNS:
        if column not in existing:
            con.execute(f"ALTER TABLE trade_intents ADD COLUMN {column} {column_type}")

    # These indexes can only be created after every legacy table has migrated.
    con.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_intents_canonical_key "
        "ON trade_intents(canonical_key) WHERE canonical_key IS NOT NULL"
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_intents_run_id ON trade_intents(run_id)")
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_intents_qualification "
        "ON trade_intents(purpose, source, action, created_at)"
    )


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
        _migrate_trade_intent_provenance(con)
        yield con
    except Exception:
        con.rollback()
        raise
    else:
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
        row = con.execute("SELECT value FROM job_markers WHERE name = ?", [name]).fetchone()
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


def _insert_intent(con: sqlite3.Connection, intent: dict[str, Any]) -> int:
    cur = con.execute(
        """
        INSERT INTO trade_intents
          (created_at, symbol, action, confidence, target_pct,
           stop_loss, take_profit, time_in_force, source, schema_version, raw_json,
           purpose, canonical_key, run_id, strategy_version, quote_provider, quote_as_of)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            intent.get("purpose"),
            intent.get("canonical_key"),
            intent.get("run_id"),
            intent.get("strategy_version"),
            intent.get("quote_provider"),
            intent.get("quote_as_of"),
        ),
    )
    if cur.lastrowid is None:
        raise sqlite3.DatabaseError("trade intent insert returned no row ID")
    return cur.lastrowid


def log_intent(
    intent: dict[str, Any],
    *,
    connection: sqlite3.Connection | None = None,
) -> int:
    """Persist an intent, optionally inside a caller-owned transaction."""
    if connection is not None:
        return _insert_intent(connection, intent)
    with _conn() as con:
        return _insert_intent(con, intent)


def get_intent_by_canonical_key(
    canonical_key: str,
    *,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    """Read one canonical intent without changing any persisted provenance."""
    if connection is not None:
        cursor = connection.execute(
            "SELECT * FROM trade_intents WHERE canonical_key = ?",
            (canonical_key,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        columns = (description[0] for description in cursor.description or ())
        return dict(zip(columns, row, strict=True))
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM trade_intents WHERE canonical_key = ?",
            (canonical_key,),
        ).fetchone()
        return dict(row) if row is not None else None


# ─── risk_decisions ───────────────────────────────────────────────────────────


def log_decision(
    intent_id: int,
    verdict: str,
    reason: str | None,
    gates: dict[str, bool],
    config_snapshot: dict[str, Any],
    *,
    connection: sqlite3.Connection | None = None,
) -> int:
    def insert(con: sqlite3.Connection) -> int:
        cur = con.execute(
            """
            INSERT INTO risk_decisions
              (decided_at, intent_id, verdict, reason, gates_json, config_json)
            VALUES (?,?,?,?,?,?)
            """,
            (
                _now(),
                intent_id,
                verdict,
                reason,
                json.dumps(gates),
                json.dumps(config_snapshot, default=str),
            ),
        )
        if cur.lastrowid is None:
            raise sqlite3.DatabaseError("risk decision insert returned no row ID")
        return cur.lastrowid

    if connection is not None:
        return insert(connection)
    with _conn() as con:
        return insert(con)


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
            (
                _now(),
                intent_id,
                decision_id,
                mode,
                client_order_id,
                broker_order_id,
                status,
                symbol,
                action,
                qty,
                target_price,
                fill_price,
                fill_qty,
                error,
                json.dumps(response, default=str) if response else None,
            ),
        )
        return cur.lastrowid


# ─── counters / history ───────────────────────────────────────────────────────


def count_orders_today(
    mode: str | None = None,
    approved_only: bool = True,
    now: datetime | None = None,
) -> int:
    """Count orders inside the current America/New_York calendar day.

    Args:
        mode: Pass mode='paper' to filter to paper orders only.
        approved_only: When True (default), count actionable BUY/SELL rows that
            may have consumed capacity: status SIMULATED, SUBMITTED, FILLED, or
            ERROR with a positive submitted/executed quantity. REJECTED is
            excluded; ERROR still consumes the daily cap because a broker or
            network failure can occur after an order was accepted. False
            deliberately returns every audit row inside the same ET bounds.
        now: Optional timezone-aware instant for deterministic callers/tests.
    """
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("count_orders_today now must be timezone-aware")
    et = ZoneInfo("America/New_York")
    et_day = instant.astimezone(et).date()
    start_utc = datetime.combine(et_day, time.min, tzinfo=et).astimezone(UTC)
    end_utc = datetime.combine(et_day + timedelta(days=1), time.min, tzinfo=et).astimezone(UTC)

    sql = "SELECT COUNT(*) AS n FROM orders WHERE placed_at >= ? AND placed_at < ?"
    params: list[Any] = [start_utc.isoformat(), end_utc.isoformat()]
    if approved_only:
        sql += (
            " AND status IN ('SIMULATED', 'SUBMITTED', 'FILLED', 'ERROR')"
            " AND action IN ('BUY', 'SELL')"
            " AND (COALESCE(qty, 0) > 0 OR COALESCE(fill_qty, 0) > 0)"
        )
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
    Each is owned elsewhere (not this module's _DDL). One missing table is
    expected (engine has no paper_trades; product may have no paper_outcomes)
    and is skipped. If NEITHER table is readable, raise LedgerUnavailable —
    that is not a fabricated $0 flat day (Astra R3). Other SQLite errors raise.
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    total = 0.0
    seen = 0
    with _conn() as con:
        try:
            row = con.execute(
                "SELECT COALESCE(SUM(pnl_usd), 0.0) AS s FROM paper_outcomes WHERE exit_at >= ?",
                [today + "T00:00:00+00:00"],
            ).fetchone()
            total += float(row["s"] or 0.0)
            seen += 1
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e).lower():
                raise
        try:
            row = con.execute(
                "SELECT COALESCE(SUM(realized_pnl), 0.0) AS s FROM paper_trades "
                "WHERE exit_time IS NOT NULL AND substr(exit_time, 1, 10) = ?",
                [today],
            ).fetchone()
            total += float(row["s"] or 0.0)
            seen += 1
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e).lower():
                raise
    if seen == 0:
        raise LedgerUnavailable(
            "neither paper_outcomes nor paper_trades is readable"
        )
    return total


# ─── paper book (positions + stops) ───────────────────────────────────────────


def paper_open_positions() -> dict[str, dict[str, float]]:
    """Net open paper positions reconstructed from SIMULATED paper fills.

    Returns ``{symbol: {"qty", "cost_basis", "avg_cost"}}`` using the
    average-cost method: BUY fills add qty/cost, SELL fills reduce qty and cost
    proportionally. Only ``status='SIMULATED' AND mode='paper'`` rows count —
    REJECTED/SKIPPED/ERROR audit rows never create a position.

    This is the source of truth execution sizing must use in paper mode: the
    real Robinhood holdings in the snapshot don't contain paper positions, so
    sizing SELLs against them collapsed every close to qty=0 (the "0 closed
    trades / phantom position" failure).
    """
    with _conn() as con:
        rows = con.execute(
            "SELECT symbol, action, fill_qty, fill_price FROM orders "
            "WHERE mode = 'paper' AND status = 'SIMULATED' "
            "AND action IN ('BUY', 'SELL') "
            "AND fill_qty IS NOT NULL AND fill_price IS NOT NULL "
            "ORDER BY id",
        ).fetchall()

    book: dict[str, dict[str, float]] = {}
    for r in rows:
        sym = r["symbol"]
        qty = float(r["fill_qty"] or 0.0)
        price = float(r["fill_price"] or 0.0)
        if qty <= 0:
            continue
        cur = book.get(sym, {"qty": 0.0, "cost_basis": 0.0})
        if r["action"] == "BUY":
            cur = {"qty": cur["qty"] + qty, "cost_basis": cur["cost_basis"] + qty * price}
        else:  # SELL — reduce at average cost; ignore sells beyond the position
            if cur["qty"] <= 0:
                continue
            sell_qty = min(qty, cur["qty"])
            avg = cur["cost_basis"] / cur["qty"]
            cur = {"qty": cur["qty"] - sell_qty, "cost_basis": cur["cost_basis"] - sell_qty * avg}
        book[sym] = cur

    out: dict[str, dict[str, float]] = {}
    for sym, cur in book.items():
        if cur["qty"] > 1e-9:
            out[sym] = {
                "qty": round(cur["qty"], 6),
                "cost_basis": round(cur["cost_basis"], 4),
                "avg_cost": round(cur["cost_basis"] / cur["qty"], 6),
            }
    return out


def record_stop(
    symbol: str,
    entry_price: float,
    stop_price: float,
    take_profit_price: float | None = None,
    volatility_tier: str | None = None,
    order_row_id: int | None = None,
) -> int:
    """Persist an exit stop for a paper entry so the EOD sweep has a real level
    to compare against (holdings never carry a stop_loss field)."""
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO paper_stops
              (created_at, order_row_id, symbol, entry_price, stop_price,
               take_profit_price, volatility_tier, active)
            VALUES (?,?,?,?,?,?,?,1)
            """,
            (
                _now(),
                order_row_id,
                symbol,
                entry_price,
                stop_price,
                take_profit_price,
                volatility_tier,
            ),
        )
        return cur.lastrowid


def active_stops() -> dict[str, dict[str, Any]]:
    """Latest active stop per symbol: {symbol: {stop_price, take_profit_price, ...}}."""
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM paper_stops WHERE active = 1 ORDER BY id",
        ).fetchall()
    return {r["symbol"]: dict(r) for r in rows}  # later rows win per symbol


def deactivate_stops(symbol: str) -> None:
    """Retire all active stops for a symbol (position fully closed)."""
    with _conn() as con:
        con.execute(
            "UPDATE paper_stops SET active = 0 WHERE symbol = ? AND active = 1",
            (symbol,),
        )


def recent_orders(limit: int = 25) -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def recent_intents(limit: int = 25) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM trade_intents ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
