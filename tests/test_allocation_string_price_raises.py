"""A string current_price is not None, so the filter compares it and TypeErrors."""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac


def test_string_price_raises_type_error(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["scanner_timeframe"] = "1HR"
    cfg["scanner_price_min"] = 5.0
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    with pytest.raises(TypeError):
        ac.validate_action(
            "BUY",
            "NVDA",
            100.0,
            open_positions=0,
            current_cash=100_000,
            current_price="12.50",
        )
