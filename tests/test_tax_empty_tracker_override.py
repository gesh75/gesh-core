"""Empty ``GESH_TRACKER_DB`` is falsy and falls through — same footgun as
#66's empty ``GESH_DB_PATH`` / ``GESH_CONFIG_PATH``.

A launchd blank must not be treated as an explicit path (that would try to
open ``Path("")``). It must continue to ``GESH_TRADING_HOME`` then cwd so the
wash-sale clock stays on the real book.
"""
from __future__ import annotations

from gesh_core import tax_harvester as th


def test_empty_tracker_db_falls_through_to_trading_home(tmp_path, monkeypatch):
    home = tmp_path / "engine"
    home.mkdir()
    monkeypatch.setenv("GESH_TRACKER_DB", "")
    monkeypatch.setenv("GESH_TRADING_HOME", str(home))
    assert th._primary_db() == home / "gesh_financial.db"


def test_empty_tracker_db_and_home_fall_through_to_cwd(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_TRACKER_DB", "")
    monkeypatch.setenv("GESH_TRADING_HOME", "")
    monkeypatch.chdir(tmp_path)
    assert th._primary_db() == tmp_path / "gesh_financial.db"
