"""Tests for gesh_core.db_path — the SINGLE resolver shared by db.py and
trading/state.py.

Astra R7: resolve_db_path is path-only. CREATE/DROP probes and mkdir belong
on an explicit bootstrap (ensure_db_writable), not import or path resolution.
Importing db.py / trading.state against a read-only operational sentinel
must not mutate it.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from gesh_core.db_path import resolve_db_path

_SRC = Path(__file__).resolve().parents[1] / "src"


def _clean_env(**extra: str) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("GESH_DB_PATH", None)
    env["PYTHONPATH"] = str(_SRC)
    env.update(extra)
    return env


def test_env_override_wins(tmp_path, monkeypatch):
    target = tmp_path / "explicit.db"
    monkeypatch.setenv("GESH_DB_PATH", str(target))
    assert resolve_db_path() == target
    assert not target.exists()


def test_cwd_default(tmp_path, monkeypatch):
    monkeypatch.delenv("GESH_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    assert resolve_db_path() == tmp_path / "gesh_financial.db"
    assert not (tmp_path / "gesh_financial.db").exists()


def test_resolve_db_path_does_not_create_missing_file(tmp_path, monkeypatch):
    target = tmp_path / "missing.db"
    monkeypatch.setenv("GESH_DB_PATH", str(target))
    assert resolve_db_path() == target
    assert not target.exists()


def test_resolve_db_path_does_not_mkdir_parents(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "dir" / "x.db"
    monkeypatch.setenv("GESH_DB_PATH", str(target))
    assert resolve_db_path() == target
    assert not (tmp_path / "nested").exists()


def test_resolve_db_path_does_not_mutate_existing_file(tmp_path, monkeypatch):
    target = tmp_path / "ops.db"
    payload = b"operational-sentinel-v1"
    target.write_bytes(payload)
    before = target.stat()
    monkeypatch.setenv("GESH_DB_PATH", str(target))
    assert resolve_db_path() == target
    after = target.stat()
    assert target.read_bytes() == payload
    assert after.st_size == before.st_size
    assert after.st_mtime_ns == before.st_mtime_ns


def test_resolve_db_path_does_not_open_corrupt_file(tmp_path, monkeypatch):
    """Path resolution must not fail-closed by probing. Corrupt bytes stay
    untouched; writability is an explicit bootstrap concern."""
    target = tmp_path / "corrupt.db"
    target.write_bytes(b"not a sqlite database")
    monkeypatch.setenv("GESH_DB_PATH", str(target))
    assert resolve_db_path() == target
    assert target.read_bytes() == b"not a sqlite database"


def test_ensure_db_writable_fails_closed_on_corrupt(tmp_path, monkeypatch):
    from gesh_core.db_path import ensure_db_writable

    target = tmp_path / "corrupt.db"
    target.write_bytes(b"not a sqlite database")
    monkeypatch.setenv("GESH_DB_PATH", str(target))
    with pytest.raises(sqlite3.DatabaseError):
        ensure_db_writable(target)


def test_ensure_db_writable_explicit_path_does_not_warn_cwd_split(
    tmp_path, caplog, monkeypatch
):
    import logging

    from gesh_core.db_path import ensure_db_writable

    monkeypatch.delenv("GESH_DB_PATH", raising=False)
    target = tmp_path / "explicit.db"
    with caplog.at_level(logging.WARNING, logger="gesh_core.db_path"):
        ensure_db_writable(target)
    assert "cwd-resolved" not in caplog.text


def test_ensure_db_writable_creates_parent_and_probes(tmp_path):
    from gesh_core.db_path import ensure_db_writable

    target = tmp_path / "nested" / "dir" / "ok.db"
    out = ensure_db_writable(target)
    assert out == target
    assert target.exists()
    con = sqlite3.connect(target)
    try:
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    assert "_state_probe" not in names


def test_ensure_db_writable_leaves_no_probe_table(tmp_path):
    from gesh_core.db_path import ensure_db_writable

    target = tmp_path / "probe.db"
    ensure_db_writable(target)
    con = sqlite3.connect(target)
    try:
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    assert "_state_probe" not in names


def test_import_db_does_not_create_cwd_database(tmp_path):
    """Importing gesh_core.db must not CREATE/DROP against cwd."""
    proc = subprocess.run(
        [sys.executable, "-c", "from gesh_core import db"],
        cwd=tmp_path,
        env=_clean_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert not (tmp_path / "gesh_financial.db").exists()


def test_import_state_does_not_create_cwd_database(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-c", "from gesh_core.trading import state"],
        cwd=tmp_path,
        env=_clean_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert not (tmp_path / "gesh_financial.db").exists()


def test_import_against_readonly_sentinel_does_not_mutate(tmp_path):
    sentinel = tmp_path / "operational.db"
    payload = b"operational-sentinel-v1"
    sentinel.write_bytes(payload)
    sentinel.chmod(0o444)
    before = sentinel.stat()
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from gesh_core import db; from gesh_core.trading import state",
        ],
        cwd=tmp_path,
        env=_clean_env(GESH_DB_PATH=str(sentinel)),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    after = sentinel.stat()
    assert sentinel.read_bytes() == payload
    assert after.st_size == before.st_size
    assert after.st_mtime_ns == before.st_mtime_ns


def test_db_and_state_share_one_resolver():
    # Both modules must resolve through gesh_core.db_path — never independently.
    from gesh_core import db, db_path
    from gesh_core.trading import state

    assert state._resolve_db is db_path.resolve_db_path
    assert db_path.ensure_db_writable is not None
    assert isinstance(db.DB_PATH, Path)
