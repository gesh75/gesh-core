"""Price filter is not entry-only — a drifted name cannot SELL/TRIM either."""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac


@pytest.mark.parametrize("action", ["SELL", "TRIM"])
@pytest.mark.parametrize("price,fragment", [(12.50, "above"), (0.05, "below")])
def test_exit_outside_stock_band_is_price_filter(tmp_path, monkeypatch, action, price, fragment):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["scanner_timeframe"] = "stock"
    cfg["scanner_price_min"] = 0.10
    cfg["scanner_price_max"] = 10.00
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    result = ac.validate_action(
        action,
        "XYZ",
        800.0,
        open_positions=1,
        current_cash=200.0,
        current_price=price,
    )
    assert result.ok is False
    assert result.code == "PRICE_FILTER"
    assert fragment in result.reason
