"""GESH_CONFIG_PATH="" (launchd/.env empty) must fall back to cwd, not Path('').

An empty override resolving to the process CWD is the documented default;
resolving to a relative empty path would write a live-execution gate file
in an unexpected place.
"""
from __future__ import annotations

from pathlib import Path

import gesh_core.allocation_config as ac


def test_empty_gesh_config_path_falls_back_to_cwd(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_CONFIG_PATH", "")
    monkeypatch.chdir(tmp_path)
    assert ac._config_path() == Path(tmp_path) / "gesh_config.json"
