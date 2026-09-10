"""A JSON array root degrades to defaults and leaves the file on disk.

``load_config`` only iterates ``stored.items()`` when the root is a dict.
A truncated-or-hand-edited ``[…]`` must not raise and must not enable
``auto_trade``. Same fail-soft contract as a null/true/string root.
"""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_json_array_root_degrades_to_defaults_and_keeps_file(tmp_path, monkeypatch):
    path = tmp_path / "gesh_config.json"
    path.write_text("[1, 2, 3]")
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    cfg = ac.load_config()
    assert cfg["auto_trade"] is False
    assert cfg["max_stock_per_trade"] == ac.DEFAULT_CONFIG["max_stock_per_trade"]
    assert json.loads(path.read_text()) == [1, 2, 3]
