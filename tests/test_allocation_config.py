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


def _write_live_config(tmp_path, monkeypatch, **overrides):
    """Persist a config with auto_trade ON so later gates are reachable."""
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))
    return cfg


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
        ok, reason = ac.validate_action(
            action, "NVDA", 100.0, open_positions=5, current_cash=550.0
        )
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


# ─── boundary type validation (PR-2) ──────────────────────────────────────────

def test_wrong_type_numeric_falls_back_to_default(tmp_path, monkeypatch):
    # A hand-edited '"max_stock_per_trade": "9999"' must not reach the execution
    # gate as a str (trade_usd > "9999" raises TypeError inside validate_action).
    p = tmp_path / "gesh_config.json"
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True                   # reach the size-cap check
    cfg["max_stock_per_trade"] = "9999"
    p.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(p))

    loaded = ac.load_config()
    assert loaded["max_stock_per_trade"] == 5000.0         # default restored

    ok, reason = ac.validate_action("BUY", "NVDA", trade_usd=6000,
                                    open_positions=0, current_cash=100_000)
    assert ok is False and "exceeds max" in reason         # gate works, no TypeError


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
    cfg["max_open_positions"] = 8            # valid int
    cfg["stock_allocation_pct"] = 55         # int for a float key — accepted
    cfg["total_buying_power"] = 25_000.0     # None-default runtime key
    p.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(p))

    loaded = ac.load_config()
    assert loaded["max_open_positions"] == 8
    assert loaded["stock_allocation_pct"] == 55.0
    assert loaded["total_buying_power"] == 25_000.0


def test_unknown_keys_still_pass_through(tmp_path, monkeypatch):
    # Forward-compat: a newer consumer's extra key survives a round-trip.
    p = tmp_path / "gesh_config.json"
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["future_knob"] = {"nested": True}
    p.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(p))
    assert ac.load_config()["future_knob"] == {"nested": True}


def test_update_config_rejects_wrong_type(tmp_path, monkeypatch):
    _write_live_config(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="auto_trade"):
        ac.update_config(auto_trade="yes")


def test_update_config_rejects_unknown_key(tmp_path, monkeypatch):
    _write_live_config(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Unknown config key"):
        ac.update_config(not_a_real_knob=1)


def test_options_trade_uses_options_cap_not_stock_cap(tmp_path, monkeypatch):
    _write_live_config(tmp_path, monkeypatch)
    # 3500 is under the $5000 stock cap but over the $2000 options cap.
    ok, reason = ac.validate_action(
        "BUY", "NVDA", 3_500.0, 0, current_cash=100_000, is_options=True
    )
    assert ok is False
    assert "options" in reason
    ok, _ = ac.validate_action(
        "BUY", "NVDA", 3_500.0, 0, current_cash=100_000, is_options=False
    )
    assert ok is True


def test_sell_and_trim_ignore_position_and_cash_floors(tmp_path, monkeypatch):
    """Exits must not be blocked by the entry-only position/cash gates."""
    _write_live_config(tmp_path, monkeypatch)
    for action in ("SELL", "TRIM"):
        ok, reason = ac.validate_action(
            action, "NVDA", 100.0, open_positions=5, current_cash=10.0
        )
        assert ok is True, (action, reason)


def test_daily_timeframe_skips_scanner_price_filter(tmp_path, monkeypatch):
    _write_live_config(tmp_path, monkeypatch, scanner_timeframe="daily")
    ok, reason = ac.validate_action(
        "BUY", "NVDA", 100.0, 0, current_cash=100_000, current_price=0.01
    )
    assert ok is True, reason


def test_intraday_enforces_price_floor_but_not_the_penny_ceiling(tmp_path, monkeypatch):
    _write_live_config(tmp_path, monkeypatch, scanner_timeframe="1HR")
    ok, reason = ac.validate_action(
        "BUY", "PENNY", 100.0, 0, current_cash=100_000, current_price=0.01
    )
    assert ok is False
    assert "below scanner minimum" in reason

    # $50 is above scanner_price_max ($10), but 1HR is not a PRICE_CAPPED mode.
    ok, reason = ac.validate_action(
        "BUY", "NVDA", 100.0, 0, current_cash=100_000, current_price=50.0
    )
    assert ok is True, reason


def test_stock_mode_enforces_price_ceiling(tmp_path, monkeypatch):
    _write_live_config(tmp_path, monkeypatch, scanner_timeframe="stock")
    ok, reason = ac.validate_action(
        "BUY", "NVDA", 100.0, 0, current_cash=100_000, current_price=50.0
    )
    assert ok is False
    assert "above scanner maximum" in reason


def test_nonpositive_price_max_disables_ceiling(tmp_path, monkeypatch):
    _write_live_config(
        tmp_path, monkeypatch, scanner_timeframe="stock", scanner_price_max=0
    )
    ok, reason = ac.validate_action(
        "BUY", "NVDA", 100.0, 0, current_cash=100_000, current_price=50.0
    )
    assert ok is True, reason


def test_get_allocation_summary_scales_buying_power(tmp_path, monkeypatch):
    _write_live_config(
        tmp_path, monkeypatch, stock_allocation_pct=70.0, options_allocation_pct=30.0
    )
    summary = ac.get_allocation_summary(buying_power=10_000.0)
    assert summary["stock_allocation_usd"] == 7_000.0
    assert summary["options_allocation_usd"] == 3_000.0
    assert summary["remaining_usd"] == 0.0
    assert summary["auto_trade"] is True
