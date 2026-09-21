"""Unknown scanner_timeframe must fall back to the daily yfinance window.

A typo in gesh_config.json must not KeyError the scanner or invent an
intraday interval that hammers Yahoo.
"""
from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_unknown_scanner_timeframe_falls_back_to_daily(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["scanner_timeframe"] = "not-a-mode"
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    params = ac.get_scanner_params()
    assert params == ac.SCANNER_MODES["daily"]
    assert params["interval"] == "1d"
    assert params["period"] == "60d"
