"""Finite negative trade_usd skips SIZE_CAP and inflates remaining cash."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_negative_size_skips_cap_and_cash_floor(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["max_stock_per_trade"] = 5000.0
    cfg["min_cash_buffer"] = 500.0
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    negative = ac.validate_action("BUY", "NVDA", -100.0, open_positions=0, current_cash=600.0)
    assert negative.ok is True
    assert negative.code == "OK"

    over_cap = ac.validate_action("BUY", "NVDA", 5001.0, open_positions=0, current_cash=100_000.0)
    assert over_cap.ok is False
    assert over_cap.code == "SIZE_CAP"

    cash_floor = ac.validate_action("BUY", "NVDA", 150.0, open_positions=0, current_cash=600.0)
    assert cash_floor.ok is False
    assert cash_floor.code == "CASH_FLOOR"
