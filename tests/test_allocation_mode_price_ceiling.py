"""Price ceiling is mode-aware; the min still fires on every non-daily mode.

``PRICE_CAPPED_MODES`` is only ``{"stock"}``. Intraday/forex modes enforce
``scanner_price_min`` but must not invent a $10 ceiling that would block
NVDA on the 1HR scanner. Pin both sides so a mode leak is a test failure.
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


def test_stock_mode_blocks_price_above_ceiling(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, scanner_timeframe="stock", scanner_price_max=10.0)
    ok, reason = ac.validate_action(
        "BUY", "NVDA", 100.0, open_positions=0, current_cash=100_000, current_price=15.0
    )
    assert ok is False
    assert "above scanner maximum" in reason


def test_intraday_mode_does_not_apply_price_ceiling(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, scanner_timeframe="1HR", scanner_price_max=10.0)
    ok, reason = ac.validate_action(
        "BUY", "NVDA", 100.0, open_positions=0, current_cash=100_000, current_price=15.0
    )
    assert ok is True, reason


def test_intraday_mode_still_enforces_price_floor(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, scanner_timeframe="1HR", scanner_price_min=0.10)
    ok, reason = ac.validate_action(
        "BUY", "PENNY", 100.0, open_positions=0, current_cash=100_000, current_price=0.01
    )
    assert ok is False
    assert "below scanner minimum" in reason
