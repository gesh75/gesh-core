"""``get_allocation_summary(buying_power=0)`` treats 0 as missing.

``bp = buying_power or cfg.get("total_buying_power") or 0`` is falsy-or,
so an explicit zero does not pin the header at $0 — it falls through to
the stored total. Pin that so a later ``is None`` change is intentional.
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


def test_zero_buying_power_arg_falls_through_to_config(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, total_buying_power=25_000.0)
    summary = ac.get_allocation_summary(buying_power=0)
    assert summary["total_buying_power"] == 25_000.0
    assert summary["stock_allocation_usd"] == 17_500.0
    assert summary["options_allocation_usd"] == 7_500.0


def test_zero_arg_and_missing_config_total_reports_zero(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, total_buying_power=None)
    summary = ac.get_allocation_summary(buying_power=0)
    assert summary["total_buying_power"] == 0
    assert summary["stock_allocation_usd"] == 0.0
    assert summary["options_allocation_usd"] == 0.0
