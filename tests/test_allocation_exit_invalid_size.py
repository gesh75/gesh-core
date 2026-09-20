"""SELL/TRIM ignore dirty cash, but a poisoned size must still fail closed."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_sell_trim_reject_nonfinite_size(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    for action in ("SELL", "TRIM"):
        for size in (float("nan"), float("inf"), float("-inf"), True, "100"):
            result = ac.validate_action(
                action, "NVDA", size, open_positions=1, current_cash=100_000
            )
            assert result.ok is False, (action, size)
            assert "Invalid trade size" in result.reason
            assert result.code == "INVALID_SIZE"
