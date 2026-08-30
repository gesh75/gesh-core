"""Boundary pins for validate_action cash/cap/position checks.

``current_cash is None`` must skip the buffer (hosts that have not loaded a
snapshot yet). Exact cap is allowed (``>``), but sitting at max open positions
is blocked (``>=``). Off-by-one here either oversizes a live trade or traps
capital.
"""
from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def _auto_on(tmp_path, monkeypatch, **overrides) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_missing_current_cash_skips_buffer_check(tmp_path, monkeypatch):
    _auto_on(tmp_path, monkeypatch)
    ok, reason = ac.validate_action("BUY", "NVDA", 3500.0, 0, current_cash=None)
    assert ok is True, reason

    ok, reason = ac.validate_action("BUY", "NVDA", 3500.0, 0, current_cash=3600.0)
    assert ok is False
    assert "minimum buffer" in reason


def test_trade_usd_equal_to_cap_is_allowed(tmp_path, monkeypatch):
    _auto_on(tmp_path, monkeypatch, max_stock_per_trade=5000.0)
    ok, reason = ac.validate_action("BUY", "NVDA", 5000.0, 0, current_cash=100_000)
    assert ok is True, reason

    ok, reason = ac.validate_action("BUY", "NVDA", 5000.01, 0, current_cash=100_000)
    assert ok is False
    assert "exceeds max" in reason


def test_open_positions_at_max_blocks_buy_but_one_below_passes(tmp_path, monkeypatch):
    _auto_on(tmp_path, monkeypatch, max_open_positions=5)
    ok, reason = ac.validate_action("BUY", "NVDA", 100.0, 5, current_cash=100_000)
    assert ok is False
    assert "max open positions" in reason

    ok, reason = ac.validate_action("BUY", "NVDA", 100.0, 4, current_cash=100_000)
    assert ok is True, reason


def test_remaining_cash_equal_to_buffer_is_allowed(tmp_path, monkeypatch):
    _auto_on(tmp_path, monkeypatch, min_cash_buffer=500.0)
    ok, reason = ac.validate_action("BUY", "NVDA", 3500.0, 0, current_cash=4000.0)
    assert ok is True, reason

    ok, reason = ac.validate_action("BUY", "NVDA", 3500.0, 0, current_cash=3999.0)
    assert ok is False
    assert "minimum buffer" in reason
