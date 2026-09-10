"""Default ``daily`` scanner mode never applies the price min/max gate.

``validate_action`` only inspects ``current_price`` when
``scanner_timeframe != "daily"``. The default config is daily, so a penny
or a mega-cap can still pass the execution gate — pin that so a later
always-on filter is an intentional change, not a silent tighten.
"""

from __future__ import annotations

import json
from pathlib import Path

import gesh_core.allocation_config as ac


def _isolate(tmp_path: Path, monkeypatch, **overrides: object) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_daily_timeframe_ignores_price_below_scanner_min(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, scanner_timeframe="daily")
    ok, reason = ac.validate_action(
        "BUY", "PENNY", 100.0, open_positions=0, current_cash=100_000, current_price=0.01
    )
    assert ok is True, reason


def test_daily_timeframe_ignores_price_above_scanner_max(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, scanner_timeframe="daily")
    ok, reason = ac.validate_action(
        "BUY", "NVDA", 100.0, open_positions=0, current_cash=100_000, current_price=9_999.0
    )
    assert ok is True, reason
