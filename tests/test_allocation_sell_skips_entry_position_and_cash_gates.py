"""SELL/TRIM skip POSITION_CAP and CASH_FLOOR so a full book can still exit."""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac


@pytest.mark.parametrize("action", ["SELL", "TRIM"])
def test_exit_ignores_full_book_and_low_cash(tmp_path, monkeypatch, action):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["max_open_positions"] = 5
    cfg["min_cash_buffer"] = 500.0
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    exit_ok = ac.validate_action(action, "NVDA", 100.0, open_positions=5, current_cash=10.0)
    assert exit_ok.ok is True
    assert exit_ok.code == "OK"

    entry = ac.validate_action("BUY", "NVDA", 100.0, open_positions=5, current_cash=10.0)
    assert entry.ok is False
    assert entry.code in {"POSITION_CAP", "CASH_FLOOR"}
