"""_growth_path clamps historical CAGR into [terminal, 60%].

A 100→300 year is a 200% CAGR; without the 60% cap the first projection
year would explode FCF. A shrinking name (100→50) has CAGR −50%, which is
floored at terminal — the model never projects contraction. Both bounds
are load-bearing methodology guards.
"""
from __future__ import annotations

import pytest

from gesh_core.dcf.fair_value import _growth_path


def test_explosive_cagr_is_capped_at_sixty_percent():
    path = _growth_path((100.0, 300.0), terminal=0.03, years=5)
    assert len(path) == 5
    assert path[0] == pytest.approx(0.60)
    assert path[-1] == pytest.approx(0.03)
    assert all(path[i] >= path[i + 1] for i in range(len(path) - 1))


def test_negative_cagr_is_floored_at_terminal_growth():
    path = _growth_path((100.0, 50.0), terminal=0.03, years=5)
    assert path == pytest.approx([0.03] * 5)
