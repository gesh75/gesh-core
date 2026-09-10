"""Named scanner modes must keep their yfinance period/interval pairing.

``get_scanner_params`` is what the hub fetch uses. A drift of ``stock`` onto
daily 60d/1d (or ``1HR`` onto 5m) would silently change the universe the
execution gate just validated against.
"""

from __future__ import annotations

import json
from pathlib import Path

import gesh_core.allocation_config as ac


def _isolate(tmp_path: Path, monkeypatch, timeframe: str) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["scanner_timeframe"] = timeframe
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_stock_mode_uses_penny_universe_bars(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, "stock")
    params = ac.get_scanner_params()
    assert params["period"] == "30d"
    assert params["interval"] == "1d"


def test_one_hour_mode_uses_intraday_bars(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, "1HR")
    params = ac.get_scanner_params()
    assert params["period"] == "5d"
    assert params["interval"] == "1h"
