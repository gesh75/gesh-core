"""A zero dollar cap blocks every positive trade; $0.00 still passes SIZE_CAP."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_zero_stock_cap_halts_positive_size(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["max_stock_per_trade"] = 0.0
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    blocked = ac.validate_action("BUY", "NVDA", 0.01, open_positions=0, current_cash=100_000.0)
    assert blocked.ok is False
    assert blocked.code == "SIZE_CAP"

    zero = ac.validate_action("BUY", "NVDA", 0.0, open_positions=0, current_cash=100_000.0)
    assert zero.ok is True
    assert zero.code == "OK"
