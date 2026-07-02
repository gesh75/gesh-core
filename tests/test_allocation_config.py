"""Parity tests for gesh_core.allocation_config (Phase 3.1 extraction).

Pins the behavior that the engine/product shims depend on:
  - the module is served from gesh_core (proves the move, not a stale local copy)
  - validate_action gate logic (auto-trade, caps, positions, cash buffer)
  - config path is cwd-relative with a GESH_CONFIG_PATH override, so each
    consumer repo keeps its OWN gesh_config.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import gesh_core.allocation_config as ac


def test_module_loads_from_gesh_core():
    assert "gesh_core" in (ac.__file__ or ""), ac.__file__


def test_defaults_present_and_safe():
    # Live execution gates must default OFF.
    assert ac.DEFAULT_CONFIG["auto_trade"] is False
    assert ac.DEFAULT_CONFIG["paper_mode"] is False
    assert ac.DEFAULT_CONFIG["min_cash_buffer"] == 500.0


def test_validate_action_auto_trade_off_blocks():
    # With a fresh config dir (auto_trade default False) a BUY is blocked.
    ok, reason = ac.validate_action("BUY", "XYZ", 100.0, 0, current_cash=100_000)
    assert ok is False
    assert "Auto-trade is OFF" in reason


def test_validate_action_respects_cwd_config(tmp_path, monkeypatch):
    # Point config at a temp dir with auto_trade ON; gate logic should engage.
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    (tmp_path / "gesh_config.json").write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(tmp_path / "gesh_config.json"))

    # under cap, room for positions, cash ok -> allowed
    ok, reason = ac.validate_action("BUY", "NVDA", 3500.0, 1, current_cash=100_000)
    assert ok is True, reason

    # exceeds per-trade cap -> blocked
    ok, reason = ac.validate_action("BUY", "NVDA", 999_999.0, 1, current_cash=100_000)
    assert ok is False
    assert "exceeds max" in reason

    # at max open positions -> blocked
    ok, reason = ac.validate_action("BUY", "NVDA", 100.0, 5, current_cash=100_000)
    assert ok is False
    assert "max open positions" in reason

    # cash buffer floor -> blocked
    ok, reason = ac.validate_action("BUY", "NVDA", 100.0, 1, current_cash=550.0)
    assert ok is False
    assert "minimum buffer" in reason


def test_config_path_override(tmp_path, monkeypatch):
    target = tmp_path / "custom.json"
    monkeypatch.setenv("GESH_CONFIG_PATH", str(target))
    assert ac._config_path() == target


def test_config_path_defaults_to_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("GESH_CONFIG_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    assert ac._config_path() == Path(tmp_path) / "gesh_config.json"


def test_get_scanner_params_default_daily(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_CONFIG_PATH", str(tmp_path / "gesh_config.json"))
    params = ac.get_scanner_params()
    assert params["interval"] == "1d"


def test_default_config_never_mutated(tmp_path, monkeypatch):
    # load_config on a fresh dir used to pass DEFAULT_CONFIG itself to save_config,
    # which stamped last_updated INTO the module-level defaults (shared-object
    # mutation). The defaults must stay pristine.
    monkeypatch.setenv("GESH_CONFIG_PATH", str(tmp_path / "gesh_config.json"))
    before = dict(ac.DEFAULT_CONFIG)
    cfg = ac.load_config()
    assert ac.DEFAULT_CONFIG == before
    assert ac.DEFAULT_CONFIG["last_updated"] is None
    assert cfg["last_updated"] is not None                 # saved copy IS stamped


def test_save_config_does_not_mutate_input(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_CONFIG_PATH", str(tmp_path / "gesh_config.json"))
    src = dict(ac.DEFAULT_CONFIG)
    out = ac.save_config(src)
    assert src["last_updated"] is None                     # input untouched
    assert out["last_updated"] is not None


def test_corrupt_config_degrades_to_defaults(tmp_path, monkeypatch):
    p = tmp_path / "gesh_config.json"
    p.write_text('{"auto_trade": tru')                     # truncated write
    monkeypatch.setenv("GESH_CONFIG_PATH", str(p))
    cfg = ac.load_config()                                 # must not raise
    assert cfg["auto_trade"] is False
    assert p.read_text().startswith('{"auto_trade": tru')  # corrupt file preserved
