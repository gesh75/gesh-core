"""Shared SQLite path resolution for db.py and trading/state.py.

Both modules MUST point at the SAME gesh_financial.db: the daily-loss circuit
breaker (``trading.state.paper_realized_pnl_usd_today``) reads the paper books
that ``db.py``'s DDL owns, so divergent resolution (one module falling back to
/tmp while the other stays cwd-relative) silently splits the audit trail and
the breaker reads an empty book. This module is the single resolver both import.

Resolution: ``GESH_DB_PATH`` env → ``<cwd>/gesh_financial.db`` (each consumer
repo keeps its OWN book, rule #44 — servers/autopilot/chain run from their repo
root). The primary is probed with a real DDL round-trip because VirtioFS
(macOS shared mount) can't do SQLite DDL/WAL from a sandbox; on failure every
importer shares the same /tmp fallback file.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

FALLBACK_DB_PATH = Path("/tmp/gesh_trading_state.db")


def resolve_db_path() -> Path:
    """Resolve the writable gesh_financial.db path (probe + shared fallback)."""
    env_override = os.getenv("GESH_DB_PATH")
    primary = Path(env_override or (Path.cwd() / "gesh_financial.db"))
    existed = primary.exists()
    try:
        primary.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(primary))
        try:
            con.execute("CREATE TABLE IF NOT EXISTS _state_probe (id INTEGER)")
            con.execute("DROP TABLE IF EXISTS _state_probe")
        finally:
            con.close()
        if not existed and env_override is None:
            # A cwd-resolved path that didn't exist means the probe just created
            # a FRESH DB. If the real book lives elsewhere (process launched from
            # the wrong directory) this silently splits the audit trail and
            # resets the daily order-rate counter. Loud, not fatal.
            logger.warning(
                "created NEW state DB at %s (cwd-resolved). If an existing "
                "gesh_financial.db lives elsewhere, launch from the repo root "
                "or set GESH_DB_PATH.", primary,
            )
        return primary
    except (sqlite3.Error, OSError) as e:
        logger.warning(
            "gesh_financial.db not writable at %s (%s) — falling back to %s",
            primary, e, FALLBACK_DB_PATH,
        )
        return FALLBACK_DB_PATH
