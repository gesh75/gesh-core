"""Invalid size is checked before live permission — R1 must not hide INVALID_SIZE."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_auto_trade_off_still_rejects_nonfinite_size(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = False
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    result = ac.validate_action(
        "BUY", "NVDA", float("nan"), open_positions=0, current_cash=100_000
    )
    assert result.ok is False
    assert result.code == "INVALID_SIZE"
    assert "Auto-trade" not in result.reason


def test_paper_skip_still_rejects_nonfinite_size(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = False
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    result = ac.validate_action(
        "BUY",
        "NVDA",
        float("inf"),
        open_positions=0,
        current_cash=100_000,
        require_live_permission=False,
    )
    assert result.ok is False
    assert result.code == "INVALID_SIZE"
