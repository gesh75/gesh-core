"""Hand-edited gesh_config.json can be valid JSON that is not an object.

``load_config`` already degrades a JSON *array* to defaults. ``null``, ``true``,
and a bare number take the same ``not a dict`` branch — they must keep
``auto_trade`` OFF and leave the corrupt file on disk for inspection.
"""
from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def _point(tmp_path, monkeypatch, text: str):
    path = tmp_path / "gesh_config.json"
    path.write_text(text)
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))
    return path


def test_json_null_degrades_to_safe_defaults(tmp_path, monkeypatch) -> None:
    path = _point(tmp_path, monkeypatch, "null")
    loaded = ac.load_config()
    assert loaded["auto_trade"] is False
    assert loaded["max_stock_per_trade"] == 5000.0
    assert path.read_text() == "null"


def test_json_true_degrades_to_safe_defaults(tmp_path, monkeypatch) -> None:
    path = _point(tmp_path, monkeypatch, "true")
    loaded = ac.load_config()
    assert loaded["auto_trade"] is False
    assert path.read_text() == "true"


def test_json_number_degrades_to_safe_defaults(tmp_path, monkeypatch) -> None:
    path = _point(tmp_path, monkeypatch, "0")
    loaded = ac.load_config()
    assert loaded["auto_trade"] is False
    assert json.loads(path.read_text()) == 0
