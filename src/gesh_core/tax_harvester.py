"""
tax_harvester.py — Tax-Loss Harvesting & Wash-Sale Tracker

Scans Robinhood positions for unrealised losses above a configurable
threshold and flags them as TAX-LOSS ELIGIBLE.  Tracks 30-day wash-sale
windows per ticker in SQLite so you don't accidentally rebuy too soon.

Key functions
─────────────
  scan_tax_loss_candidates(positions, cost_basis_map)
      → list of {ticker, loss_usd, loss_pct, wash_safe_date, days_until_safe, status}

  record_harvest(ticker, sale_price, loss_usd)
      → writes to wash_sale_log; starts 30-day window

  get_wash_status(ticker)
      → {in_wash_window: bool, wash_safe_date: str, days_remaining: int}

  get_harvest_summary()
      → {total_harvestable_loss, candidates, wash_active}

DB table (auto-created in gesh_financial.db)
─────────────────────────────────────────────
  wash_sale_log: id, ticker, sale_date, sale_price, loss_usd, wash_safe_date, created_at
"""

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from math import isfinite
from pathlib import Path
from typing import Any

# ─── Money (M4) ───────────────────────────────────────────────────────────────
# This is a tax ledger of record (wash-sale loss tracking), so monetary math runs
# in Decimal quantized to cents — float drift must not accumulate across summed
# losses. Inputs arrive as floats from the broker; Decimal(str(x)) takes their
# decimal repr (not the binary-dust expansion). Values are converted back to float
# only at the boundary for JSON/SQLite, already rounded to the cent.
_CENTS = Decimal("0.01")


def _money(x: Any) -> Decimal:
    """Coerce a float/int/str to an exact Decimal via its decimal repr."""
    return Decimal(str(x or 0))


def _cents(d: Decimal) -> float:
    """Quantize a Decimal to cents and return a float for storage/serialization."""
    return float(d.quantize(_CENTS, rounding=ROUND_HALF_UP))


# ─── Config ───────────────────────────────────────────────────────────────────

MIN_LOSS_USD: float = 500.0   # minimum unrealised loss to flag
WASH_SALE_DAYS: int = 30      # IRS wash-sale window

logger = logging.getLogger(__name__)


def _primary_db() -> Path:
    """Resolve the tracker DB (holds the wash_sale_log table).

    gesh-core can't derive the path from ``__file__`` (that points inside the
    installed package, not either consumer repo), so resolution is env-driven —
    matching the product repo's existing ``GESH_TRACKER_DB`` / ``GESH_TRADING_HOME``
    conventions. Resolved at call time so env set by entry-point scripts (and
    tests) always takes effect:

      1. ``GESH_TRACKER_DB``   — explicit path to gesh_financial.db (preferred).
      2. ``GESH_TRADING_HOME`` — engine repo root → ``<home>/gesh_financial.db``.
      3. ``<cwd>/gesh_financial.db`` — the engine runs from its own root, so this
         preserves the old ``__file__.parent`` behavior for the engine; the
         product wires GESH_TRACKER_DB in its launchd start scripts because its
         cwd is the product root, not the engine's.
    """
    env = os.environ.get("GESH_TRACKER_DB")
    if env:
        return Path(env)
    home = os.environ.get("GESH_TRADING_HOME")
    if home:
        return Path(home) / "gesh_financial.db"
    return Path.cwd() / "gesh_financial.db"


def _db_path() -> Path:
    """Resolve and verify the wash-sale database, failing closed on errors."""
    primary = _primary_db()
    try:
        primary.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(primary), timeout=5)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS _probe (x INTEGER)")
            conn.execute("DROP TABLE IF EXISTS _probe")
        finally:
            conn.close()
        return primary
    except (sqlite3.Error, OSError):
        logger.exception("wash-sale database is not usable at %s", primary)
        raise


@contextmanager
def _get_conn() -> Iterator[sqlite3.Connection]:
    """Open a tracker-DB connection, commit on success, and ALWAYS close.

    sqlite3's own connection context manager commits/rolls back but never
    closes, so the previous ``with _get_conn() as conn:`` pattern leaked a
    handle on every call — accumulating across each autopilot tax scan. This
    wrapper guarantees the connection is closed in ``finally`` (matching
    db.py / trading.state). Callers may still call ``conn.commit()`` explicitly;
    the redundant commit here is harmless.
    """
    conn = sqlite3.connect(str(_db_path()), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ─── Schema ───────────────────────────────────────────────────────────────────

def init_wash_sale_table() -> None:
    """Create wash_sale_log table if it doesn't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wash_sale_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker        TEXT NOT NULL,
                sale_date     TEXT NOT NULL,
                sale_price    REAL,
                loss_usd      REAL,
                wash_safe_date TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_wsl_ticker ON wash_sale_log(ticker)")
        conn.commit()


# ─── Core helpers ─────────────────────────────────────────────────────────────

def get_wash_status(ticker: str) -> dict[str, Any]:
    """Return wash-sale window status for a ticker."""
    init_wash_sale_table()
    today_str = date.today().isoformat()
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT wash_safe_date, sale_date
               FROM wash_sale_log
               WHERE ticker = ?
               ORDER BY created_at DESC LIMIT 1""",
            (ticker.upper(),),
        ).fetchone()
    if row is None:
        return {"in_wash_window": False, "wash_safe_date": None, "days_remaining": 0}
    wash_safe = row["wash_safe_date"]
    # Inclusive: IRS Pub 550 is "within 30 days after the sale". A sale on
    # Jan 1 has a last blocked day of Jan 31 (sale + 30). `>` treated that
    # stored date as already safe, so a repurchase on wash_safe_date was a
    # wash sale and the harvested loss could be disallowed.
    in_window  = wash_safe >= today_str
    if in_window:
        days_rem = (date.fromisoformat(wash_safe) - date.today()).days
        # wash_safe_date is the last blocked day. A 0 delta still means
        # today is blocked — report 1 so days_until_safe cannot read as
        # cleared while in_wash_window is True.
        days_rem = max(1, days_rem)
    else:
        days_rem = 0
    return {
        "in_wash_window":  in_window,
        "wash_safe_date":  wash_safe,
        "days_remaining":  days_rem,
    }


def record_harvest(ticker: str, sale_price: float, loss_usd: float) -> None:
    """Log a tax-loss harvest event and start the 30-day wash-sale clock."""
    init_wash_sale_table()
    sale_date  = date.today().isoformat()
    # Last calendar day of the 30-day-after window (inclusive). get_wash_status
    # treats this date as still blocked.
    safe_date  = (date.today() + timedelta(days=WASH_SALE_DAYS)).isoformat()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO wash_sale_log (ticker, sale_date, sale_price, loss_usd, wash_safe_date)
               VALUES (?, ?, ?, ?, ?)""",
            (ticker.upper(), sale_date, sale_price, loss_usd, safe_date),
        )
        conn.commit()


# ─── Main scanner ─────────────────────────────────────────────────────────────

def scan_tax_loss_candidates(
    positions: dict[str, dict],
    cost_basis_map: dict[str, float] | None = None,
    min_loss_usd: float = MIN_LOSS_USD,
) -> list[dict[str, Any]]:
    """
    Scan positions for tax-loss harvesting opportunities.

    Parameters
    ----------
    positions : {ticker: {price, quantity, equity, ...}} from data_fetcher
    cost_basis_map : {ticker: avg_cost_per_share} from Robinhood
                     Falls back to `average_buy_price` key inside position dict.
    min_loss_usd : minimum unrealised loss (default $500)

    Returns
    -------
    List sorted by loss ascending (biggest losses first), each dict:
        ticker, current_price, cost_basis, shares,
        unrealised_loss_usd, unrealised_loss_pct,
        in_wash_window, wash_safe_date, days_until_safe,
        status  (ELIGIBLE | IN_WASH_WINDOW | PROFIT)
    """
    init_wash_sale_table()
    candidates: list[dict] = []
    cbm = cost_basis_map or {}

    for ticker, pos in positions.items():
        ticker = ticker.upper()
        price  = float(pos.get("price", 0) or 0)
        shares = float(pos.get("quantity", pos.get("shares", 0)) or 0)
        if not isfinite(price) or not isfinite(shares) or price <= 0 or shares <= 0:
            continue

        # Cost basis: from map → from position dict. NEVER fall back to the
        # current price — that fabricates a break-even and silently hides a real
        # loss (best practice: a position with unknown basis is a red flag that
        # must be surfaced and excluded from harvest, not zeroed out).
        _cb = cbm.get(ticker) or pos.get("average_buy_price")
        if not _cb:
            candidates.append({
                "ticker":              ticker,
                "current_price":       round(price, 4),
                "cost_basis":          None,
                "shares":              round(shares, 4),
                "unrealised_loss_usd": None,
                "unrealised_loss_pct": None,
                "in_wash_window":      False,
                "wash_safe_date":      None,
                "days_until_safe":     None,
                "status":              "NO_COST_BASIS",
            })
            continue
        cb = float(_cb)
        if not isfinite(cb):
            continue
        # Cent-precise loss in Decimal — float drift must not accumulate in the
        # summed harvestable total (M4).
        unrealised_d = ((_money(price) - _money(cb)) * _money(shares)).quantize(
            _CENTS, rounding=ROUND_HALF_UP
        )
        unrealised_pct = ((price - cb) / cb * 100) if cb > 0 else 0.0

        if unrealised_d >= 0:
            continue   # profitable position — skip

        wash = get_wash_status(ticker)
        loss_abs_d = -unrealised_d   # positive Decimal

        record: dict[str, Any] = {
            "ticker":               ticker,
            "current_price":        round(price, 4),
            "cost_basis":           round(cb, 4),
            "shares":               round(shares, 4),
            "unrealised_loss_usd":  float(unrealised_d),
            "unrealised_loss_pct":  round(unrealised_pct, 2),
            "in_wash_window":       wash["in_wash_window"],
            "wash_safe_date":       wash["wash_safe_date"],
            "days_until_safe":      wash["days_remaining"],
        }

        if wash["in_wash_window"]:
            record["status"] = "IN_WASH_WINDOW"
        elif loss_abs_d >= _money(min_loss_usd):
            record["status"] = "ELIGIBLE"
        else:
            record["status"] = "BELOW_THRESHOLD"

        candidates.append(record)

    # Sort by loss (biggest first); NO_COST_BASIS rows (None) sort last.
    return sorted(candidates, key=lambda x: (x["unrealised_loss_usd"] is None, x["unrealised_loss_usd"] or 0.0))


def get_harvest_summary(
    positions: dict[str, dict],
    cost_basis_map: dict[str, float] | None = None,
) -> dict[str, Any]:
    """High-level harvest summary for dashboard injection."""
    candidates = scan_tax_loss_candidates(positions, cost_basis_map)
    eligible   = [c for c in candidates if c["status"] == "ELIGIBLE"]
    in_window  = [c for c in candidates if c["status"] == "IN_WASH_WINDOW"]
    no_basis   = [c for c in candidates if c["status"] == "NO_COST_BASIS"]
    # Sum in Decimal so the harvestable total is exact to the cent (M4).
    total_harvestable = sum(
        (_money(c["unrealised_loss_usd"]).copy_abs() for c in eligible), Decimal(0)
    )
    return {
        "total_harvestable_loss_usd": _cents(total_harvestable),
        "eligible_count":            len(eligible),
        "in_wash_window_count":      len(in_window),
        "no_cost_basis_count":       len(no_basis),
        "eligible":                  eligible,
        "in_wash_window":            in_window,
        "no_cost_basis":             no_basis,
        "generated_at":              datetime.now(UTC).replace(tzinfo=None).isoformat(),
        "summary": (
            f"Tax harvest: ${total_harvestable:,.0f} eligible across "
            f"{len(eligible)} position(s). "
            f"{len(in_window)} in 30-day wash-sale window."
        ),
    }


# ─── CLI test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick smoke test with fake positions
    fake_positions = {
        "PLTR": {"price": 18.50, "quantity": 200, "average_buy_price": 24.00},
        "NVDA": {"price": 875.00, "quantity": 5,  "average_buy_price": 820.00},
        "MSTR": {"price": 320.00, "quantity": 10, "average_buy_price": 480.00},
    }
    result = get_harvest_summary(fake_positions)
    print(result["summary"])
    for c in result["eligible"]:
        print(f"  {c['ticker']:6s}  loss=${abs(c['unrealised_loss_usd']):,.0f}  "
              f"({c['unrealised_loss_pct']:.1f}%)  status={c['status']}")
