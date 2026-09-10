"""Allocation header leftover is arithmetic, not a clamped non-negative.

When stock + options percents do not sum to 100, ``remaining_usd`` is the
raw residual (including a negative leftover if the percents over-allocate).
Pin that so a later ``max(0, …)`` clamp is an intentional product change.
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


def test_summary_remainder_when_percents_under_allocate(tmp_path, monkeypatch):
    _isolate(
        tmp_path,
        monkeypatch,
        stock_allocation_pct=60.0,
        options_allocation_pct=30.0,
    )
    summary = ac.get_allocation_summary(buying_power=10_000.0)
    assert summary["stock_allocation_usd"] == 6_000.0
    assert summary["options_allocation_usd"] == 3_000.0
    assert summary["remaining_usd"] == 1_000.0


def test_summary_remainder_goes_negative_when_percents_over_allocate(tmp_path, monkeypatch):
    _isolate(
        tmp_path,
        monkeypatch,
        stock_allocation_pct=80.0,
        options_allocation_pct=40.0,
    )
    summary = ac.get_allocation_summary(buying_power=10_000.0)
    assert summary["remaining_usd"] == -2_000.0
