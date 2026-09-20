"""Shared SQLite path resolution for db.py and trading/state.py.

Both modules MUST point at the SAME gesh_financial.db: the daily-loss circuit
breaker (``trading.state.paper_realized_pnl_usd_today``) reads the paper books
that ``db.py``'s DDL owns, so divergent resolution (one module falling back to
/tmp while the other stays cwd-relative) silently splits the audit trail and
the breaker reads an empty book. This module is the single resolver both import.

Resolution: ``GESH_DB_PATH`` env → ``<cwd>/gesh_financial.db`` (each consumer
repo keeps its OWN book, rule #44 — servers/autopilot/chain run from their repo
root). Path resolution is I/O-free so import and pytest collection cannot
mutate an operational file (Astra R7). Writability is an explicit bootstrap:
``ensure_db_writable`` probes with a real DDL round-trip because VirtioFS
(macOS shared mount) can't do SQLite DDL/WAL from a sandbox. Probe failures
are fatal so sensitive state is never redirected to an insecure shared location.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_writable_lock = threading.Lock()
_writable_ok: set[str] = set()


def resolve_db_path() -> Path:
    """Return the configured gesh_financial.db path without touching the filesystem."""
    env_override = os.getenv("GESH_DB_PATH")
    return Path(env_override or (Path.cwd() / "gesh_financial.db"))


def ensure_db_writable(path: Path | str | None = None) -> Path:
    """Create parents and prove the path can run SQLite DDL.

    Call this from an explicit bootstrap (``init_db``, first ``connect`` /
    ``_conn``), never from import or ``resolve_db_path``.
    """
    cwd_defaulted = path is None and os.getenv("GESH_DB_PATH") is None
    target = resolve_db_path() if path is None else Path(path)
    key = str(target)
    if key in _writable_ok:
        return target
    with _writable_lock:
        if key in _writable_ok:
            return target
        existed = target.exists()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(str(target), timeout=30)
            try:
                con.execute("CREATE TABLE IF NOT EXISTS _state_probe (id INTEGER)")
                con.execute("DROP TABLE IF EXISTS _state_probe")
            finally:
                con.close()
        except (sqlite3.Error, OSError):
            logger.exception("gesh_financial.db is not usable at %s", target)
            raise
        if not existed and cwd_defaulted:
            # A cwd-resolved path that didn't exist means the probe just created
            # a FRESH DB. If the real book lives elsewhere (process launched from
            # the wrong directory) this silently splits the audit trail and
            # resets the daily order-rate counter. Loud, not fatal.
            logger.warning(
                "created NEW state DB at %s (cwd-resolved). If an existing "
                "gesh_financial.db lives elsewhere, launch from the repo root "
                "or set GESH_DB_PATH.",
                target,
            )
        _writable_ok.add(key)
        return target
