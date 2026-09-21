"""A dated Series mixed with a plain ndarray must use positional alignment.

``_correlation_haircuts`` date-aligns only when EVERY usable series is a
``pd.Series``. One injected ndarray must not take the date-join path (which
would TypeError) and must not fail-open the whole cluster.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gesh_core import kelly


def test_mixed_series_and_ndarray_uses_positional_fallback() -> None:
    values = np.random.default_rng(23).normal(0.001, 0.02, 30)
    dated = pd.Series(values, index=pd.bdate_range("2026-01-05", periods=30))
    hc = kelly._correlation_haircuts(
        ["A", "B"],
        {"A": dated, "B": values.copy()},
        threshold=0.7,
    )
    assert hc["A"] == pytest.approx(1 / np.sqrt(2), abs=1e-6)
    assert hc["B"] == pytest.approx(1 / np.sqrt(2), abs=1e-6)
