"""reset_config restores factory defaults without mutating DEFAULT_CONFIG.

A live-execution flip (auto_trade=True) must not survive a reset, and the
module-level defaults must stay pristine so the next load_config cannot
inherit a stamped last_updated or a raised cap.
"""
from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_reset_config_restores_safe_defaults(tmp_path, monkeypatch):
    path = tmp_path / "gesh_config.json"
    dirty = dict(ac.DEFAULT_CONFIG)
    dirty["auto_trade"] = True
    dirty["max_stock_per_trade"] = 99_000.0
    path.write_text(json.dumps(dirty))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    before = dict(ac.DEFAULT_CONFIG)
    out = ac.reset_config()
    assert ac.DEFAULT_CONFIG == before
    assert out["auto_trade"] is False
    assert out["max_stock_per_trade"] == 5000.0
    assert out["last_updated"] is not None

    reloaded = ac.load_config()
    assert reloaded["auto_trade"] is False
    assert reloaded["max_stock_per_trade"] == 5000.0
