"""Tests for gesh_core.db_path — the SINGLE resolver shared by db.py and
trading/state.py.

Divergent resolution was the highest-blast-radius core bug: state probed and
could fall back to /tmp while db.py stayed cwd-relative, splitting the audit
chain from the paper books and blinding the daily-loss circuit breaker.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gesh_core.db_path import resolve_db_path


def test_env_override_wins(tmp_path, monkeypatch):
    target = tmp_path / "explicit.db"
    monkeypatch.setenv("GESH_DB_PATH", str(target))
    assert resolve_db_path() == target


def test_cwd_default(tmp_path, monkeypatch):
    monkeypatch.delenv("GESH_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    assert resolve_db_path() == tmp_path / "gesh_financial.db"


def test_unusable_primary_fails_closed(tmp_path, monkeypatch):
    target = tmp_path / "corrupt.db"
    target.write_bytes(b"not a sqlite database")
    monkeypatch.setenv("GESH_DB_PATH", str(target))

    with pytest.raises(sqlite3.DatabaseError):
        resolve_db_path()


def test_probe_leaves_no_probe_table(tmp_path, monkeypatch):
    target = tmp_path / "probe.db"
    monkeypatch.setenv("GESH_DB_PATH", str(target))
    resolve_db_path()
    con = sqlite3.connect(target)
    try:
        names = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    finally:
        con.close()
    assert "_state_probe" not in names


def test_db_and_state_share_one_resolver():
    # Both modules must resolve through gesh_core.db_path — never independently.
    from gesh_core import db, db_path
    from gesh_core.trading import state

    assert state._resolve_db is db_path.resolve_db_path
    assert isinstance(db.DB_PATH, Path)
