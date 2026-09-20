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

import pytest

import gesh_core.allocation_config as ac
from gesh_core.trading.config import ConfigError


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


def test_validate_action_rejects_noncanonical_action(tmp_path, monkeypatch):
    """Malformed actions must fail closed instead of skipping action-specific gates."""
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    for action in ("buy", " BUY", "HOLD", ""):
        ok, reason = ac.validate_action(action, "NVDA", 100.0, open_positions=5, current_cash=550.0)
        assert ok is False
        assert "Invalid action" in reason


def test_validate_action_rejects_unhashable_action():
    """JSON arrays and objects must fail closed rather than raising TypeError."""
    for action in ([], {}):
        ok, reason = ac.validate_action(
            action, "NVDA", 100.0, open_positions=0, current_cash=100_000
        )
        assert ok is False
        assert "Invalid action" in reason


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
    assert cfg["last_updated"] is not None  # saved copy IS stamped


def test_save_config_does_not_mutate_input(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_CONFIG_PATH", str(tmp_path / "gesh_config.json"))
    src = dict(ac.DEFAULT_CONFIG)
    out = ac.save_config(src)
    assert src["last_updated"] is None  # input untouched
    assert out["last_updated"] is not None


def test_corrupt_config_degrades_to_defaults(tmp_path, monkeypatch):
    p = tmp_path / "gesh_config.json"
    p.write_text('{"auto_trade": tru')  # truncated write
    monkeypatch.setenv("GESH_CONFIG_PATH", str(p))
    cfg = ac.load_config()  # must not raise
    assert cfg["auto_trade"] is False
    assert p.read_text().startswith('{"auto_trade": tru')  # corrupt file preserved


# ─── boundary type validation (PR-2) ──────────────────────────────────────────


def test_wrong_type_numeric_fails_construction(tmp_path, monkeypatch):
    # A hand-edited '"max_stock_per_trade": "9999"' must fail construction
    # rather than silently restoring the default cap.
    p = tmp_path / "gesh_config.json"
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["max_stock_per_trade"] = "9999"
    p.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(p))

    with pytest.raises(ConfigError) as exc:
        ac.load_config()
    assert "max_stock_per_trade" in str(exc.value)
    assert "9999" not in str(exc.value)


def test_wrong_type_string_key_falls_back_not_numeric_error(tmp_path, monkeypatch):
    """Metadata strings are not numeric caps — a bad type must not fail the load."""
    p = tmp_path / "gesh_config.json"
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["scanner_timeframe"] = 1
    cfg["screener_universe"] = 2
    cfg["version"] = 1.1
    p.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(p))

    loaded = ac.load_config()
    assert loaded["scanner_timeframe"] == ac.DEFAULT_CONFIG["scanner_timeframe"]
    assert loaded["screener_universe"] == ac.DEFAULT_CONFIG["screener_universe"]
    assert loaded["version"] == ac.DEFAULT_CONFIG["version"]


def test_wrong_type_bool_fails_safe(tmp_path, monkeypatch):
    # auto_trade is the live-execution gate: a truthy non-bool ("yes", 1) must
    # fall back to the SAFE default False, never accidentally enable execution.
    p = tmp_path / "gesh_config.json"
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = "yes"
    p.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(p))

    loaded = ac.load_config()
    assert loaded["auto_trade"] is False


def test_valid_overrides_and_none_default_keys_pass_through(tmp_path, monkeypatch):
    p = tmp_path / "gesh_config.json"
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["max_open_positions"] = 8  # valid int
    cfg["stock_allocation_pct"] = 55  # int for a float key — accepted
    cfg["options_allocation_pct"] = 45  # pair must still sum to 100
    cfg["total_buying_power"] = 25_000.0  # None-default runtime key
    p.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(p))

    loaded = ac.load_config()
    assert loaded["max_open_positions"] == 8
    assert loaded["stock_allocation_pct"] == 55.0
    assert loaded["options_allocation_pct"] == 45.0
    assert loaded["total_buying_power"] == 25_000.0


def test_unknown_keys_still_pass_through(tmp_path, monkeypatch):
    # Forward-compat: a newer consumer's extra key survives a round-trip.
    p = tmp_path / "gesh_config.json"
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["future_knob"] = {"nested": True}
    p.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(p))
    assert ac.load_config()["future_knob"] == {"nested": True}


def test_update_config_rejects_wrong_type():
    import pytest

    with pytest.raises(ValueError, match="auto_trade"):
        ac.update_config(auto_trade="yes")


def test_validate_action_rejects_nonfinite_trade_usd(tmp_path, monkeypatch):
    """NaN > cap is False in IEEE-754 — a poisoned size must not pass the gate."""
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    for size in (float("nan"), float("inf"), float("-inf"), True, "100"):
        ok, reason = ac.validate_action(
            "BUY", "NVDA", size, open_positions=0, current_cash=100_000
        )
        assert ok is False, size
        assert "Invalid trade size" in reason


def test_validate_action_rejects_nonfinite_cash(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    ok, reason = ac.validate_action(
        "BUY", "NVDA", 100.0, open_positions=0, current_cash=float("nan")
    )
    assert ok is False
    assert "Invalid cash" in reason


def test_sell_trim_ignore_dirty_cash(tmp_path, monkeypatch):
    """NaN cash must not block exits — the cash floor is BUY/ADD-only."""
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    for action in ("SELL", "TRIM"):
        ok, reason = ac.validate_action(
            action, "NVDA", 100.0, open_positions=1, current_cash=float("nan")
        )
        assert ok is True, (action, reason)


def _write_cfg(tmp_path, monkeypatch, **overrides):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))
    return path


def test_validate_action_auto_trade_off_still_enforces_size_cap(tmp_path, monkeypatch):
    """Live permission OFF must not skip the per-trade dollar cap (Astra R1)."""
    _write_cfg(
        tmp_path,
        monkeypatch,
        auto_trade=False,
        max_stock_per_trade=100.0,
    )
    result = ac.validate_action("BUY", "TEST", 200.0, open_positions=0, current_cash=100_000)
    ok, reason = result
    assert ok is False
    assert "exceeds max" in reason
    assert "Auto-trade" not in reason
    assert result.code == "SIZE_CAP"


def test_validate_action_auto_trade_off_still_enforces_position_cap(tmp_path, monkeypatch):
    _write_cfg(tmp_path, monkeypatch, auto_trade=False, max_open_positions=5)
    result = ac.validate_action("BUY", "TEST", 100.0, open_positions=5, current_cash=100_000)
    assert result.ok is False
    assert "max open positions" in result.reason
    assert "Auto-trade" not in result.reason
    assert result.code == "POSITION_CAP"


def test_validate_action_auto_trade_off_still_enforces_cash_floor(tmp_path, monkeypatch):
    _write_cfg(tmp_path, monkeypatch, auto_trade=False, min_cash_buffer=500.0)
    result = ac.validate_action("BUY", "TEST", 100.0, open_positions=0, current_cash=550.0)
    assert result.ok is False
    assert "minimum buffer" in result.reason
    assert "Auto-trade" not in result.reason
    assert result.code == "CASH_FLOOR"


def test_validate_action_skip_live_permission_allows_valid_paper_trade(tmp_path, monkeypatch):
    _write_cfg(tmp_path, monkeypatch, auto_trade=False, max_stock_per_trade=5_000.0)
    result = ac.validate_action(
        "BUY",
        "TEST",
        200.0,
        open_positions=0,
        current_cash=100_000,
        require_live_permission=False,
    )
    assert result.ok is True
    assert result.reason == "OK"
    assert result.code == "OK"


def test_validate_action_skip_live_permission_still_blocks_over_cap(tmp_path, monkeypatch):
    _write_cfg(tmp_path, monkeypatch, auto_trade=False, max_stock_per_trade=100.0)
    result = ac.validate_action(
        "BUY",
        "TEST",
        200.0,
        open_positions=0,
        current_cash=100_000,
        require_live_permission=False,
    )
    assert result.ok is False
    assert result.code == "SIZE_CAP"


def test_validate_action_live_request_still_blocked_when_auto_trade_off(tmp_path, monkeypatch):
    """A valid live request with auto_trade OFF is still permission-blocked."""
    _write_cfg(tmp_path, monkeypatch, auto_trade=False, max_stock_per_trade=5_000.0)
    result = ac.validate_action("BUY", "TEST", 200.0, open_positions=0, current_cash=100_000)
    assert result.ok is False
    assert "Auto-trade is OFF" in result.reason
    assert result.code == "LIVE_PERMISSION"


def test_validate_action_auto_trade_on_over_cap_unchanged(tmp_path, monkeypatch):
    _write_cfg(tmp_path, monkeypatch, auto_trade=True, max_stock_per_trade=100.0)
    result = ac.validate_action("BUY", "TEST", 200.0, open_positions=0, current_cash=100_000)
    assert result.ok is False
    assert result.code == "SIZE_CAP"
