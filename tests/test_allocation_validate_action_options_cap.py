"""``validate_action(is_options=True)`` routes to the options per-trade cap.

Stock and options caps are independent. A $2500 options ticket must be blocked
by the $2000 options cap even though it is under the $5000 stock cap, and the
reason string must say ``options``. Pin the branch so a later shared-cap
refactor cannot silently let options through the stock gate.
"""
from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def _enable_auto_trade(tmp_path, monkeypatch, **overrides) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_options_trade_uses_options_cap_not_stock(tmp_path, monkeypatch) -> None:
    _enable_auto_trade(tmp_path, monkeypatch)
    ok, reason = ac.validate_action(
        "BUY", "NVDA", 2500.0, open_positions=0, current_cash=100_000, is_options=True
    )
    assert ok is False
    assert "options" in reason
    assert "stock" not in reason


def test_same_size_stock_trade_is_under_stock_cap(tmp_path, monkeypatch) -> None:
    _enable_auto_trade(tmp_path, monkeypatch)
    ok, reason = ac.validate_action(
        "BUY", "NVDA", 2500.0, open_positions=0, current_cash=100_000, is_options=False
    )
    assert ok is True, reason


def test_options_trade_under_options_cap_is_allowed(tmp_path, monkeypatch) -> None:
    _enable_auto_trade(tmp_path, monkeypatch)
    ok, reason = ac.validate_action(
        "BUY", "NVDA", 1500.0, open_positions=0, current_cash=100_000, is_options=True
    )
    assert ok is True, reason
