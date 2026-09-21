"""R6 leftover: an unreadable config path degrades instead of raising.

Corrupt JSON is pinned on main. A GESH_CONFIG_PATH that points at a directory
(or other OSError) must not fail construction — callers treat load_config as
the safe bootstrap, and a launch-from-wrong-cwd directory path would otherwise
take down the gate.
"""

from __future__ import annotations

import gesh_core.allocation_config as ac


def test_directory_config_path_degrades_to_defaults(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GESH_CONFIG_PATH", str(tmp_path))
    cfg = ac.load_config()
    assert cfg["auto_trade"] is False
    assert cfg["max_stock_per_trade"] == ac.DEFAULT_CONFIG["max_stock_per_trade"]
    assert cfg["stock_allocation_pct"] == ac.DEFAULT_CONFIG["stock_allocation_pct"]
    assert list(tmp_path.iterdir()) == []
