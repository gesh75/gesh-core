"""R1 leftover: leftover scanner modes still apply the price floor.

#76 pins daily skip + stock ceiling vs 1HR min-only. #82 pins 1HR beating
LIVE_PERMISSION. 5MIN / premarket / forex are not daily and are not in
PRICE_CAPPED_MODES — a cheap print must still be PRICE_FILTER, but a $50
print must not invent a ceiling.
"""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac


def _write_cfg(tmp_path, monkeypatch, **overrides) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


@pytest.mark.parametrize(
    "mode,period,interval",
    [
        ("5MIN", "1d", "5m"),
        ("premarket", "1d", "5m"),
        ("forex-1HR", "5d", "1h"),
        ("forex-4HR", "10d", "4h"),
        ("forex-daily", "60d", "1d"),
    ],
)
def test_leftover_modes_apply_price_min_not_ceiling(
    tmp_path, monkeypatch, mode, period, interval
) -> None:
    _write_cfg(
        tmp_path,
        monkeypatch,
        auto_trade=True,
        scanner_timeframe=mode,
        scanner_price_min=0.10,
        scanner_price_max=10.00,
    )
    cheap = ac.validate_action(
        "BUY",
        "PENNY",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=0.05,
    )
    assert cheap.ok is False
    assert cheap.code == "PRICE_FILTER"
    assert "below scanner minimum" in cheap.reason

    expensive = ac.validate_action(
        "BUY",
        "SPY",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=50.0,
    )
    assert expensive.ok is True
    assert expensive.code == "OK"

    params = ac.get_scanner_params()
    assert params["period"] == period
    assert params["interval"] == interval
