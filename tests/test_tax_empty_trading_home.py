"""Empty GESH_TRADING_HOME is falsy and falls through to cwd.

Distinct from an empty GESH_TRACKER_DB (which is truthy and would be used
as the path). A launchd plist that sets TRADING_HOME="" must not resolve
to ``/gesh_financial.db``.
"""

from __future__ import annotations

from pathlib import Path

from gesh_core import tax_harvester as th


def test_empty_trading_home_falls_through_to_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("GESH_TRACKER_DB", raising=False)
    monkeypatch.setenv("GESH_TRADING_HOME", "")
    monkeypatch.chdir(tmp_path)
    assert th._primary_db() == Path(tmp_path) / "gesh_financial.db"


def test_whitespace_trading_home_is_kept_as_a_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("GESH_TRACKER_DB", raising=False)
    monkeypatch.setenv("GESH_TRADING_HOME", "   ")
    assert th._primary_db() == Path("   ") / "gesh_financial.db"
