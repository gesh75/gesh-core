"""``update_config`` must persist a valid typed write, not only reject bad ones.

The live-execution gate is flipped through this path. A save that stamps
``last_updated`` but drops the caller's ``auto_trade=True`` would leave
autopilot thinking the gate is on while disk still says off.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import gesh_core.allocation_config as ac


def test_update_config_persists_valid_auto_trade_and_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(dict(ac.DEFAULT_CONFIG)))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    out = ac.update_config(auto_trade=True, max_open_positions=7)
    assert out["auto_trade"] is True
    assert out["max_open_positions"] == 7
    assert out["last_updated"] is not None

    reloaded = ac.load_config()
    assert reloaded["auto_trade"] is True
    assert reloaded["max_open_positions"] == 7
