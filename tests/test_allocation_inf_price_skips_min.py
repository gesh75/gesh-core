"""+inf current_price is not below the floor; stock ceiling still catches it."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def _enable(tmp_path, monkeypatch, *, timeframe: str) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["scanner_timeframe"] = timeframe
    cfg["scanner_price_min"] = 5.0
    cfg["scanner_price_max"] = 10.0
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_inf_price_passes_1hr_min(tmp_path, monkeypatch):
    """1HR has no ceiling — inf < 5 is False, so an infinite quote is admitted."""
    _enable(tmp_path, monkeypatch, timeframe="1HR")
    result = ac.validate_action(
        "BUY",
        "NVDA",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=float("inf"),
    )
    assert result.ok is True
    assert result.code == "OK"


def test_inf_price_hits_stock_ceiling(tmp_path, monkeypatch):
    """stock mode ceiling: inf > 10 is True, so the same quote is PRICE_FILTER."""
    _enable(tmp_path, monkeypatch, timeframe="stock")
    result = ac.validate_action(
        "BUY",
        "NVDA",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=float("inf"),
    )
    assert result.ok is False
    assert result.code == "PRICE_FILTER"
