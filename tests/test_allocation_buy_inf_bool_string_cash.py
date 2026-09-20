"""BUY leftover cash types: inf / bool / string must fail closed (NaN is on main)."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_buy_rejects_inf_bool_and_string_cash(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    for cash in (float("inf"), float("-inf"), True, False, "10000.00"):
        result = ac.validate_action(
            "BUY", "NVDA", 100.0, open_positions=0, current_cash=cash
        )
        assert result.ok is False, cash
        assert "Invalid cash" in result.reason
        assert result.code == "INVALID_CASH"
