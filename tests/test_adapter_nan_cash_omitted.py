"""Host cash/equity junk must not enter the ledger as IEEE NaN/Inf.

``_finite_or_none`` is the adapter boundary: a Yahoo/Robinhood ``NaN`` cash
field would otherwise hash as a float and fork snapshot identity (or fail
canonicalization). None is the documented "unknown scalar" encoding.
"""

from __future__ import annotations

import math

import pytest

from gesh_core.ledger.adapters.daily_analysis import _finite_or_none


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (12.5, 12.5),
        (0, 0.0),
        ("1000", 1000.0),
        (None, None),
        ("N/A", None),
        ("", None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        (object(), None),
    ],
)
def test_finite_or_none_coerces_or_drops(value, expected):
    out = _finite_or_none(value)
    if expected is None:
        assert out is None
    else:
        assert out == pytest.approx(expected)
        assert math.isfinite(out)
