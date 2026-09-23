"""Bool open_positions subclasses int — True/False are treated as 1/0, not invalid."""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac


@pytest.mark.parametrize("count", [True, False])
def test_bool_open_count_is_not_a_full_book(tmp_path, monkeypatch, count):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg["max_open_positions"] = 5
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    blocked = ac.validate_action("BUY", "NVDA", 100.0, open_positions=5, current_cash=100_000.0)
    assert blocked.ok is False
    assert blocked.code == "POSITION_CAP"

    slipped = ac.validate_action("BUY", "NVDA", 100.0, open_positions=count, current_cash=100_000.0)
    assert slipped.ok is True
    assert slipped.code == "OK"
