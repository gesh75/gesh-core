"""Named scanner modes not pinned by #76 must keep their yfinance pairing.

``get_scanner_params`` is what the hub fetch uses. Drifting ``5MIN`` onto
daily bars, or ``forex-4HR`` onto 1h, silently changes the universe the
execution gate just validated against.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import gesh_core.allocation_config as ac


def _isolate(tmp_path: Path, monkeypatch, timeframe: str) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["scanner_timeframe"] = timeframe
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


@pytest.mark.parametrize(
    "timeframe,period,interval",
    [
        ("5MIN", "1d", "5m"),
        ("premarket", "1d", "5m"),
        ("forex-1HR", "5d", "1h"),
        ("forex-4HR", "10d", "4h"),
        ("forex-daily", "60d", "1d"),
    ],
)
def test_leftover_scanner_modes_keep_period_interval(
    tmp_path, monkeypatch, timeframe: str, period: str, interval: str
) -> None:
    _isolate(tmp_path, monkeypatch, timeframe)
    params = ac.get_scanner_params()
    assert params["period"] == period
    assert params["interval"] == interval
