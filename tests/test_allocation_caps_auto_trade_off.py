"""R1 leftover: options size and ADD position caps still run when auto_trade is OFF.

#77 covered stock BUY size/position/cash. Options use a different dollar cap,
and ADD is an entry that must not sneak past POSITION_CAP as LIVE_PERMISSION.
"""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def _write_cfg(tmp_path, monkeypatch, **overrides) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_validate_action_options_cap_auto_trade_off(tmp_path, monkeypatch) -> None:
    _write_cfg(
        tmp_path,
        monkeypatch,
        auto_trade=False,
        max_options_per_trade=2000.0,
        max_stock_per_trade=50_000.0,
    )
    result = ac.validate_action(
        "BUY",
        "NVDA",
        3000.0,
        open_positions=0,
        current_cash=100_000,
        is_options=True,
    )
    assert result.ok is False
    assert result.code == "SIZE_CAP"
    assert "options" in result.reason
    assert "Auto-trade" not in result.reason


def test_validate_action_add_position_cap_auto_trade_off(tmp_path, monkeypatch) -> None:
    _write_cfg(tmp_path, monkeypatch, auto_trade=False, max_open_positions=5)
    result = ac.validate_action("ADD", "NVDA", 100.0, open_positions=5, current_cash=100_000)
    assert result.ok is False
    assert result.code == "POSITION_CAP"
    assert "max open positions" in result.reason
    assert "Auto-trade" not in result.reason
