"""+inf open_positions compares >= cap and blocks; NaN leftover is the opposite hole."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_inf_open_positions_is_position_cap(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["max_open_positions"] = 5
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    result = ac.validate_action(
        "BUY", "NVDA", 100.0, open_positions=float("inf"), current_cash=100_000.0
    )
    assert result.ok is False
    assert result.code == "POSITION_CAP"
