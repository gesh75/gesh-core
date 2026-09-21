"""Boundary coercion the open allocation PRs do not cover.

Hand-edited gesh_config.json can smuggle bools into numeric caps (bool
subclasses int) or replace the object with a JSON array. Those must fail
closed to defaults — otherwise validate_action can see True as 1 open-position
slot, or crash before the auto-trade gate.
"""
from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def _point_config(tmp_path, monkeypatch, payload) -> None:
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(payload) if not isinstance(payload, str) else payload)
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_bool_numeric_caps_fall_back_to_defaults(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["max_open_positions"] = True  # bool subclasses int
    cfg["max_stock_per_trade"] = False
    _point_config(tmp_path, monkeypatch, cfg)

    loaded = ac.load_config()
    assert loaded["max_open_positions"] == 5
    assert loaded["max_stock_per_trade"] == 5000.0

    ok, reason = ac.validate_action(
        "BUY", "NVDA", trade_usd=100.0, open_positions=5, current_cash=100_000
    )
    assert ok is False
    assert "max open positions" in reason


def test_int_for_bool_gate_fails_safe(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = 1
    cfg["paper_mode"] = 1
    _point_config(tmp_path, monkeypatch, cfg)

    loaded = ac.load_config()
    assert loaded["auto_trade"] is False
    assert loaded["paper_mode"] is False


def test_json_array_config_degrades_to_defaults(tmp_path, monkeypatch):
    _point_config(tmp_path, monkeypatch, [1, 2, 3])
    loaded = ac.load_config()
    assert loaded["auto_trade"] is False
    assert loaded["max_stock_per_trade"] == 5000.0


def test_unknown_scanner_timeframe_falls_back_to_daily(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["scanner_timeframe"] = "not-a-mode"
    _point_config(tmp_path, monkeypatch, cfg)
    assert ac.get_scanner_params() == ac.SCANNER_MODES["daily"]


def test_reset_config_restores_safe_defaults(tmp_path, monkeypatch):
    _point_config(tmp_path, monkeypatch, dict(ac.DEFAULT_CONFIG))
    ac.update_config(auto_trade=True, max_open_positions=9)
    out = ac.reset_config()
    assert out["auto_trade"] is False
    assert out["max_open_positions"] == 5
