"""Operator-facing allocation dollar math.

``get_allocation_summary`` is what the report header shows as deployable
capital. A 70/30 split that reports the wrong ``remaining_usd`` would let an
operator think they have headroom they do not.
"""

from __future__ import annotations

import json
from pathlib import Path

import gesh_core.allocation_config as ac


def _isolate(tmp_path: Path, monkeypatch, **overrides: object) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_explicit_buying_power_drives_dollar_split(tmp_path: Path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch, stock_allocation_pct=60.0, options_allocation_pct=30.0)
    summary = ac.get_allocation_summary(buying_power=100_000.0)
    assert summary["total_buying_power"] == 100_000.0
    assert summary["stock_allocation_usd"] == 60_000.0
    assert summary["options_allocation_usd"] == 30_000.0
    assert summary["remaining_usd"] == 10_000.0
    assert summary["stock_allocation_pct"] == 60.0
    assert summary["options_allocation_pct"] == 30.0


def test_explicit_buying_power_overrides_config_total(tmp_path: Path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch, total_buying_power=50_000.0)
    summary = ac.get_allocation_summary(buying_power=10_000.0)
    assert summary["total_buying_power"] == 10_000.0
    assert summary["stock_allocation_usd"] == 7_000.0
    assert summary["options_allocation_usd"] == 3_000.0


def test_config_total_used_when_arg_omitted(tmp_path: Path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch, total_buying_power=25_000.0)
    summary = ac.get_allocation_summary()
    assert summary["total_buying_power"] == 25_000.0
    assert summary["stock_allocation_usd"] == 17_500.0
    assert summary["options_allocation_usd"] == 7_500.0
    assert summary["remaining_usd"] == 0.0


def test_missing_buying_power_reports_zero_dollars(tmp_path: Path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch, total_buying_power=None)
    summary = ac.get_allocation_summary()
    assert summary["total_buying_power"] == 0
    assert summary["stock_allocation_usd"] == 0.0
    assert summary["options_allocation_usd"] == 0.0
    assert summary["remaining_usd"] == 0.0


def test_summary_echoes_live_gates_from_config(tmp_path: Path, monkeypatch) -> None:
    _isolate(
        tmp_path,
        monkeypatch,
        auto_trade=True,
        paper_mode=True,
        min_cash_buffer=750.0,
        max_open_positions=8,
    )
    summary = ac.get_allocation_summary(buying_power=1.0)
    assert summary["auto_trade"] is True
    assert summary["paper_mode"] is True
    assert summary["min_cash_buffer"] == 750.0
    assert summary["max_open_positions"] == 8
