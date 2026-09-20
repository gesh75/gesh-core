"""SELL/TRIM must still exit when the broker cash snapshot is bool/inf/string."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_sell_trim_ignore_bool_inf_and_string_cash(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    for action in ("SELL", "TRIM"):
        for cash in (float("inf"), float("-inf"), True, False, "not-cash"):
            result = ac.validate_action(
                action, "NVDA", 100.0, open_positions=1, current_cash=cash
            )
            assert result.ok is True, (action, cash, result.reason)
            assert result.code == "OK"
