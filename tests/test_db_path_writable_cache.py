"""R7 leftover: ensure_db_writable caches a successful probe per path.

A second call must not open SQLite again. The no-arg form must honor
GESH_DB_PATH (resolution stays I/O-free; bootstrap is explicit).
"""

from __future__ import annotations

import sqlite3

import pytest

from gesh_core import db_path


@pytest.fixture(autouse=True)
def _clear_writable_cache():
    db_path._writable_ok.clear()
    yield
    db_path._writable_ok.clear()


def test_second_call_uses_cache_and_skips_reprobe(tmp_path, monkeypatch) -> None:
    target = tmp_path / "cached.db"
    opens: list[str] = []
    real_connect = sqlite3.connect

    def tracking_connect(*args, **kwargs):
        opens.append(str(args[0]) if args else "")
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(db_path.sqlite3, "connect", tracking_connect)
    first = db_path.ensure_db_writable(target)
    assert first == target
    assert target.exists()
    assert len(opens) == 1
    second = db_path.ensure_db_writable(target)
    assert second == target
    assert len(opens) == 1


def test_no_arg_uses_env_override(tmp_path, monkeypatch) -> None:
    target = tmp_path / "from-env.db"
    monkeypatch.setenv("GESH_DB_PATH", str(target))
    out = db_path.ensure_db_writable()
    assert out == target
    assert target.exists()
