"""NaN open_positions >= max is False — the position cap fails open."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_nan_open_positions_does_not_hit_cap(tmp_path, monkeypatch):
    """A missing/poisoned book count must not be treated as room under max_open_positions."""
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["max_open_positions"] = 5
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    finite_at_cap = ac.validate_action("BUY", "NVDA", 100.0, open_positions=5, current_cash=100_000)
    assert finite_at_cap.ok is False
    assert finite_at_cap.code == "POSITION_CAP"

    poisoned = ac.validate_action(
        "BUY", "NVDA", 100.0, open_positions=float("nan"), current_cash=100_000
    )
    assert poisoned.ok is True
    assert poisoned.code == "OK"
