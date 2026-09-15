"""R7 leftover: cwd-split warning only when resolve defaulted AND created a new file.

#81 pinned that an explicit path does not warn. The positive contract — a
cwd-resolved create is loud, an existing cwd book is not, and an env
override is not — was untested.
"""

from __future__ import annotations

import logging
import sqlite3

from gesh_core.db_path import ensure_db_writable, resolve_db_path


def test_ensure_db_writable_cwd_default_warns_on_create(tmp_path, caplog, monkeypatch) -> None:
    monkeypatch.delenv("GESH_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "gesh_financial.db"
    with caplog.at_level(logging.WARNING, logger="gesh_core.db_path"):
        out = ensure_db_writable()
    assert out == target
    assert target.exists()
    assert "cwd-resolved" in caplog.text


def test_ensure_db_writable_cwd_existing_file_does_not_warn(tmp_path, caplog, monkeypatch) -> None:
    monkeypatch.delenv("GESH_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "gesh_financial.db"
    con = sqlite3.connect(target)
    con.close()
    with caplog.at_level(logging.WARNING, logger="gesh_core.db_path"):
        ensure_db_writable()
    assert "cwd-resolved" not in caplog.text


def test_ensure_db_writable_env_override_create_does_not_warn(
    tmp_path, caplog, monkeypatch
) -> None:
    target = tmp_path / "from-env.db"
    monkeypatch.setenv("GESH_DB_PATH", str(target))
    assert resolve_db_path() == target
    with caplog.at_level(logging.WARNING, logger="gesh_core.db_path"):
        out = ensure_db_writable()
    assert out == target
    assert target.exists()
    assert "cwd-resolved" not in caplog.text
