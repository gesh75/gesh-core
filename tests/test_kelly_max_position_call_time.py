"""``_max_position_pct`` honors env at CALL time, not just import time.

``MAX_POSITION_PCT`` is an import-time constant for consensus/dashboard
importers. Sizing itself must pick up a live ``KELLY_MAX_POSITION_PCT``
change in a long-lived autopilot without a process restart.
"""

from __future__ import annotations

import pytest

from gesh_core import kelly


def test_call_time_position_cap_reads_current_env(monkeypatch):
    monkeypatch.setenv("KELLY_MAX_POSITION_PCT", "0.10")
    assert kelly._max_position_pct() == pytest.approx(0.10)


def test_call_time_position_cap_out_of_range_uses_import_fallback(monkeypatch):
    monkeypatch.setenv("KELLY_MAX_POSITION_PCT", "1.5")
    assert kelly._max_position_pct() == pytest.approx(kelly.MAX_POSITION_PCT)
