"""String open_positions is not guarded — the cap comparison raises TypeError."""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac


def test_string_open_positions_crashes_instead_of_action_check(tmp_path, monkeypatch):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["max_open_positions"] = 5
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    with pytest.raises(TypeError):
        ac.validate_action("BUY", "NVDA", 100.0, open_positions="5", current_cash=100_000.0)
