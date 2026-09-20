"""None current_price skips PRICE_FILTER even in an intraday mode that has a floor."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_missing_price_does_not_run_intraday_floor(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["scanner_timeframe"] = "1HR"
    cfg["scanner_price_min"] = 5.0
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    result = ac.validate_action(
        "BUY",
        "PENNY",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=None,
    )
    assert result.ok is True
    assert result.code == "OK"

    blocked = ac.validate_action(
        "BUY",
        "PENNY",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=1.0,
    )
    assert blocked.ok is False
    assert blocked.code == "PRICE_FILTER"
