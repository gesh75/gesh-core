"""GESH_DB_PATH="" must not resolve to Path('') / a random relative file.

Empty env is treated as unset so db.py and trading.state stay on the shared
cwd book. A split here blinds the daily-loss breaker.
"""
from __future__ import annotations

from gesh_core.db_path import resolve_db_path


def test_empty_gesh_db_path_falls_back_to_cwd(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_DB_PATH", "")
    monkeypatch.chdir(tmp_path)
    assert resolve_db_path() == tmp_path / "gesh_financial.db"
