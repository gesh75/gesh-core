"""Leftover Kelly overlay: garbage cost env keeps the default drag.

#63 pins non-finite cost/corr overlays as IEEE. A non-numeric string must not
raise and must not become a 0-drag (which would size thin edges as frictionless).
"""

from __future__ import annotations

import pytest

from gesh_core import kelly

_DEFAULT_DRAG = (10.0 / 10_000.0) / 21.0


@pytest.mark.parametrize("bps,days", [("abc", "21"), ("10", "xyz"), ("", "")])
def test_garbage_cost_env_keeps_default_drag(monkeypatch, bps: str, days: str) -> None:
    monkeypatch.setenv("KELLY_COST_BPS", bps)
    monkeypatch.setenv("KELLY_REBALANCE_DAYS", days)
    assert kelly._cost_drag_daily() == pytest.approx(_DEFAULT_DRAG)
