"""A hand-edited gesh_config.json whose root is a JSON string must not enable
live execution. ``load_config`` only merges mapping roots; a string body
degrades to defaults and the corrupt file stays on disk for inspection.
"""
from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_json_string_root_degrades_to_defaults_and_keeps_file(tmp_path, monkeypatch):
    path = tmp_path / "gesh_config.json"
    path.write_text('"yes"')
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    cfg = ac.load_config()

    assert cfg["auto_trade"] is False
    assert cfg["paper_mode"] is False
    assert cfg["max_stock_per_trade"] == 5000.0
    assert path.read_text() == '"yes"'


def test_json_string_root_does_not_reach_validate_action(tmp_path, monkeypatch):
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps("true"))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    ok, reason = ac.validate_action("BUY", "NVDA", 100.0, 0, current_cash=100_000)
    assert ok is False
    assert "Auto-trade is OFF" in reason
