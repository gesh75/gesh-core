"""SIZE_CAP is action-agnostic — appreciated SELL/TRIM sizes are blocked too."""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac


@pytest.mark.parametrize("action", ["SELL", "TRIM"])
def test_exit_over_stock_cap_is_size_cap(tmp_path, monkeypatch, action):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["max_stock_per_trade"] = 5000.0
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    result = ac.validate_action(action, "NVDA", 6200.0, open_positions=3, current_cash=200.0)
    assert result.ok is False
    assert result.code == "SIZE_CAP"
    assert "Auto-trade" not in result.reason
