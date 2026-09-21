"""Leftover correlation haircut: a one-day overlap must fail open.

Date-aligned pairs with a mid-series gap are pinned on main. Two names that
share fewer than two calendar dates have no usable corr — they must keep
haircut 1.0 rather than be clustered on a single coincident print.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from gesh_core import kelly


def test_single_shared_date_does_not_form_a_cluster() -> None:
    left_dates = pd.bdate_range("2026-01-05", periods=20)
    right_dates = pd.bdate_range("2026-01-30", periods=20)
    shared = left_dates.intersection(right_dates)
    assert len(shared) == 1

    local = np.random.default_rng(23)
    a = pd.Series(local.normal(0.001, 0.02, 20), index=left_dates)
    b = pd.Series(local.normal(0.001, 0.02, 20), index=right_dates)
    # Identical print on the one shared date — still not enough to correlate.
    b.loc[shared[0]] = a.loc[shared[0]]

    hc = kelly._correlation_haircuts(["A", "B"], {"A": a, "B": b}, threshold=0.7)
    assert hc == {"A": 1.0, "B": 1.0}
