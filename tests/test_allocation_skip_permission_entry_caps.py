"""R1 leftover: skipping live permission still runs entry caps.

Main already pins SIZE_CAP + the happy paper path when
``require_live_permission=False``. POSITION_CAP and CASH_FLOOR must not
become OK just because the caller is paper.
"""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def _write_cfg(tmp_path, monkeypatch, **overrides) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_skip_live_permission_still_enforces_position_cap(tmp_path, monkeypatch) -> None:
    _write_cfg(tmp_path, monkeypatch, auto_trade=False, max_open_positions=5)
    result = ac.validate_action(
        "BUY",
        "TEST",
        100.0,
        open_positions=5,
        current_cash=100_000,
        require_live_permission=False,
    )
    assert result.ok is False
    assert result.code == "POSITION_CAP"
    assert "Auto-trade" not in result.reason


def test_skip_live_permission_still_enforces_cash_floor(tmp_path, monkeypatch) -> None:
    _write_cfg(tmp_path, monkeypatch, auto_trade=False, min_cash_buffer=500.0)
    result = ac.validate_action(
        "BUY",
        "TEST",
        100.0,
        open_positions=0,
        current_cash=550.0,
        require_live_permission=False,
    )
    assert result.ok is False
    assert result.code == "CASH_FLOOR"
    assert "Auto-trade" not in result.reason


def test_skip_live_permission_add_hits_position_cap(tmp_path, monkeypatch) -> None:
    _write_cfg(tmp_path, monkeypatch, auto_trade=False, max_open_positions=3)
    result = ac.validate_action(
        "ADD",
        "TEST",
        50.0,
        open_positions=3,
        current_cash=100_000,
        require_live_permission=False,
    )
    assert result.ok is False
    assert result.code == "POSITION_CAP"
