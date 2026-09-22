"""NaN current_price is not None, but NaN < min and NaN > max are both False."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def _enable_intraday(tmp_path, monkeypatch, *, timeframe: str) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["scanner_timeframe"] = timeframe
    cfg["scanner_price_min"] = 5.0
    cfg["scanner_price_max"] = 10.0
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_nan_price_skips_1hr_min(tmp_path, monkeypatch):
    """1HR has a floor only — a poisoned NaN quote is not below 5.0, so the BUY proceeds."""
    _enable_intraday(tmp_path, monkeypatch, timeframe="1HR")
    result = ac.validate_action(
        "BUY",
        "PENNY",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=float("nan"),
    )
    assert result.ok is True
    assert result.code == "OK"


def test_nan_price_skips_stock_ceiling(tmp_path, monkeypatch):
    """stock mode also has a ceiling — NaN > 10 is False, so both sides fail open."""
    _enable_intraday(tmp_path, monkeypatch, timeframe="stock")
    result = ac.validate_action(
        "BUY",
        "PENNY",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=float("nan"),
    )
    assert result.ok is True
    assert result.code == "OK"
