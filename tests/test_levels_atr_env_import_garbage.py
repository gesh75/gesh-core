"""Garbage ATR env vars crash ``trading.levels`` at import.

Unlike ``config._env_int``, ATR knobs use bare ``int()`` / ``float()`` at
module import. A bad plist entry therefore prevents paper stops, the EOD
sweep, and tracker shims from loading — no flat-ladder fallback. Pin the
crash so a later fail-open parse cannot silently start using defaults.
"""

from __future__ import annotations

import os
import subprocess
import sys


def _import_levels(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        [sys.executable, "-c", "import gesh_core.trading.levels"],
        capture_output=True,
        text=True,
        env=merged,
    )


def test_garbage_atr_period_fails_import() -> None:
    proc = _import_levels({"EQUITY_ATR_PERIOD": "garbage"})
    assert proc.returncode != 0
    assert "ValueError" in (proc.stderr + proc.stdout)


def test_garbage_atr_stop_mult_fails_import() -> None:
    proc = _import_levels({"EQUITY_ATR_STOP_MULT": "not-a-float"})
    assert proc.returncode != 0
    assert "ValueError" in (proc.stderr + proc.stdout)


def test_default_env_imports() -> None:
    env = os.environ.copy()
    for key in (
        "EQUITY_ATR_PERIOD",
        "EQUITY_ATR_STOP_MULT",
        "EQUITY_MIN_STOP_PCT",
        "EQUITY_MAX_STOP_PCT",
        "EQUITY_ATR_TARGET_MULT",
    ):
        env.pop(key, None)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from gesh_core.trading.levels import _derive_levels; "
            "print(_derive_levels('BUY', 100.0, None, None, atr_value=None))",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0
    assert "95.0" in proc.stdout or "95" in proc.stdout
