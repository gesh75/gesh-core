"""_growth_path must not divide by a non-positive first-year revenue.

If year-0 revenue is 0 or negative, CAGR is undefined. The helper must fall
back to a flat terminal path rather than exploding or inventing a 60% start.
"""

from __future__ import annotations

from gesh_core.dcf.fair_value import _growth_path


def test_growth_path_non_positive_first_year_uses_terminal():
    assert _growth_path((0.0, 110.0), terminal=0.03, years=5) == [0.03] * 5
    assert _growth_path((-10.0, 110.0), terminal=0.03, years=5) == [0.03] * 5


def test_growth_path_single_year_history_uses_terminal():
    assert _growth_path((100.0,), terminal=0.03, years=5) == [0.03] * 5
