"""EQUITY_USE_ATR_STOPS is evaluated at import time.

Only the exact tokens ``0`` / ``false`` / ``False`` disable ATR-adaptive stops.
Empty launchd/.env values and common aliases (``FALSE``, ``off``, padded
``false ``) leave the feature ON — a silent widening of every paper stop vs the
flat 5/12 ladder. Pin the allowlist so a later parse change is intentional.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest


def _atr_flag(value: str) -> bool:
    env = os.environ.copy()
    env["EQUITY_USE_ATR_STOPS"] = value
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from gesh_core.trading import levels; print(levels.EQUITY_USE_ATR_STOPS)",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.stdout.strip() == "True"


@pytest.mark.parametrize("value", ["", "FALSE", "off", "no", "false "])
def test_equity_use_atr_stops_empty_and_aliases_still_enable(value):
    assert _atr_flag(value) is True


@pytest.mark.parametrize("value", ["0", "false", "False"])
def test_equity_use_atr_stops_only_exact_disable_tokens(value):
    assert _atr_flag(value) is False
