"""Bool current_price is compared as 0/1 — True can pass a $0.10 floor as $1."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_true_price_passes_stock_floor_false_is_filtered(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["scanner_timeframe"] = "stock"
    cfg["scanner_price_min"] = 0.10
    cfg["scanner_price_max"] = 10.00
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    truthy = ac.validate_action(
        "BUY", "NVDA", 100.0, open_positions=0, current_cash=100_000.0, current_price=True
    )
    assert truthy.ok is True
    assert truthy.code == "OK"

    falsy = ac.validate_action(
        "BUY", "NVDA", 100.0, open_positions=0, current_cash=100_000.0, current_price=False
    )
    assert falsy.ok is False
    assert falsy.code == "PRICE_FILTER"
