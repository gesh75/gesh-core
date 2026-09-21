"""KILL_SWITCH_PATH env must wire through load_risk_config().

A misconfigured path means the emergency stop file is never seen and live
trading continues after operators believe they armed the kill switch.
``_kill_switch_present`` expanduser is covered elsewhere; this pins the env
binding on the config object the gate actually reads.
"""
from __future__ import annotations

from pathlib import Path

from gesh_core.trading.config import load_risk_config
from gesh_core.trading.risk_gate_core import _kill_switch_present


def test_kill_switch_path_env_override(monkeypatch, tmp_path):
    target = tmp_path / "ops" / "KILL"
    monkeypatch.setenv("KILL_SWITCH_PATH", str(target))
    cfg = load_risk_config()
    assert cfg.kill_switch_path == str(target)
    assert _kill_switch_present(cfg.kill_switch_path) is False

    target.parent.mkdir(parents=True)
    target.write_text("")
    assert _kill_switch_present(cfg.kill_switch_path) is True


def test_kill_switch_path_defaults_to_home_gesh(monkeypatch):
    monkeypatch.delenv("KILL_SWITCH_PATH", raising=False)
    cfg = load_risk_config()
    assert cfg.kill_switch_path == str(Path.home() / ".gesh" / "KILL")
