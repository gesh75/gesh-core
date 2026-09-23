"""Scanner timeframe compares case-sensitively — Daily/STOCK silently retune filters."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def _cfg(tmp_path, monkeypatch, timeframe: str) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["scanner_timeframe"] = timeframe
    cfg["scanner_price_min"] = 0.10
    cfg["scanner_price_max"] = 10.00
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_daily_skip_is_exact_lowercase(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, "daily")
    daily = ac.validate_action(
        "BUY", "PENNY", 100.0, open_positions=0, current_cash=100_000.0, current_price=0.05
    )
    assert daily.ok is True
    assert daily.code == "OK"

    _cfg(tmp_path, monkeypatch, "Daily")
    titled = ac.validate_action(
        "BUY", "PENNY", 100.0, open_positions=0, current_cash=100_000.0, current_price=0.05
    )
    assert titled.ok is False
    assert titled.code == "PRICE_FILTER"


def test_stock_ceiling_is_exact_lowercase(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch, "stock")
    stock = ac.validate_action(
        "BUY", "NVDA", 100.0, open_positions=0, current_cash=100_000.0, current_price=15.0
    )
    assert stock.ok is False
    assert stock.code == "PRICE_FILTER"

    _cfg(tmp_path, monkeypatch, "STOCK")
    upper = ac.validate_action(
        "BUY", "NVDA", 100.0, open_positions=0, current_cash=100_000.0, current_price=15.0
    )
    assert upper.ok is True
    assert upper.code == "OK"
