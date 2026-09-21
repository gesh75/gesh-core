"""Omitted buying_power must use the stored runtime total, not invent $0.

``get_allocation_summary()`` is what the report header reads. If
``total_buying_power`` is set on disk and the caller passes nothing, drifting
to $0 would understate every allocated dollar.
"""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac


def test_omitted_buying_power_uses_stored_total(tmp_path, monkeypatch) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["total_buying_power"] = 25_000.0
    cfg["stock_allocation_pct"] = 70.0
    cfg["options_allocation_pct"] = 30.0
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    summary = ac.get_allocation_summary()
    assert summary["total_buying_power"] == pytest.approx(25_000.0)
    assert summary["stock_allocation_usd"] == pytest.approx(17_500.0)
    assert summary["options_allocation_usd"] == pytest.approx(7_500.0)
    assert summary["remaining_usd"] == pytest.approx(0.0)
