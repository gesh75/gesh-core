"""JSON ``true`` on a numeric cap must not become ``1``.

``bool`` subclasses ``int``, so a missing ``isinstance(value, bool)`` guard
would load ``max_stock_per_trade: true`` as ``1.0`` and silently cap every
stock trade at $1. Load degrades to the safe default; ``update_config``
fails fast because the caller is program code.
"""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac


def test_json_true_numeric_cap_falls_back_to_default(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["max_stock_per_trade"] = True
    cfg["max_open_positions"] = True
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    loaded = ac.load_config()
    assert loaded["max_stock_per_trade"] == 5000.0
    assert loaded["max_open_positions"] == 5

    ok, reason = ac.validate_action(
        "BUY", "NVDA", trade_usd=3500.0, open_positions=1, current_cash=100_000
    )
    assert ok is True, reason


def test_update_config_rejects_bool_for_numeric_key(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_CONFIG_PATH", str(tmp_path / "gesh_config.json"))
    with pytest.raises(ValueError, match="max_stock_per_trade"):
        ac.update_config(max_stock_per_trade=True)
