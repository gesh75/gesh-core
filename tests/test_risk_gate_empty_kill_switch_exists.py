"""Blank ``KILL_SWITCH_PATH`` is treated as the switch being present.

``Path("").exists()`` is True because pathlib resolves ``""`` to cwd. Combined
with config keeping a launchd/empty env as ``""`` (not restoring ``~/.gesh/KILL``),
the kill-switch gate fires on every run with no file to delete. Pin the
``_kill_switch_present`` side of that contract; config-blank persistence is
already claimed elsewhere.
"""

from __future__ import annotations

from pathlib import Path

from gesh_core.trading.risk_gate_core import _kill_switch_present


def test_empty_kill_switch_path_is_present_because_cwd_exists() -> None:
    assert Path("").exists() is True
    assert _kill_switch_present("") is True


def test_whitespace_only_kill_switch_path_is_absent() -> None:
    # Contrast: a spaces-only path is a real relative name, not cwd.
    assert _kill_switch_present("   ") is False


def test_missing_file_is_absent(tmp_path) -> None:
    assert _kill_switch_present(str(tmp_path / "KILL")) is False
