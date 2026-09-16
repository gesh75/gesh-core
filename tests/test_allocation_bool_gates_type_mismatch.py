"""R1 leftover: non-bool paper/extended-hours tokens cannot enable a gate.

``auto_trade: "yes"`` already falls back to False on main. ``paper_mode``
and ``extended_hours`` use the same bool coerce — a truthy string or ``1``
must restore the safe default, not flip the gate.
"""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def test_paper_mode_yes_falls_back_to_false(tmp_path, monkeypatch) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["paper_mode"] = "yes"
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    loaded = ac.load_config()
    assert loaded["paper_mode"] is False


def test_extended_hours_int_falls_back_to_default(tmp_path, monkeypatch) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["extended_hours"] = 1
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    loaded = ac.load_config()
    assert loaded["extended_hours"] is ac.DEFAULT_CONFIG["extended_hours"]
    assert loaded["extended_hours"] is True


def test_paper_mode_true_bool_is_kept(tmp_path, monkeypatch) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["paper_mode"] = True
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    loaded = ac.load_config()
    assert loaded["paper_mode"] is True
