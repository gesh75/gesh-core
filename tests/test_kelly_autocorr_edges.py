"""Autocorrelation shrink: disable switch, short/flat series, floor on extreme rho.

M2 must never UP-size. An extreme lag-1 rho would otherwise drive the shrink
factor to 0 and falsely AVOID a name; the 0.30 floor is the safety bound.
"""

from __future__ import annotations

import numpy as np
import pytest

from gesh_core import kelly


def test_autocorr_shrink_disabled_via_env(monkeypatch):
    monkeypatch.setenv("KELLY_AUTOCORR_SHRINK", "0")
    rho, factor = kelly._autocorr_shrink(np.array([0.01, 0.02, 0.03, 0.04]))
    assert (rho, factor) == (0.0, 1.0)


def test_autocorr_shrink_short_or_flat_is_noop():
    assert kelly._autocorr_shrink(np.array([0.01, 0.02])) == (0.0, 1.0)
    assert kelly._autocorr_shrink(np.array([0.01, 0.01, 0.01, 0.01])) == (0.0, 1.0)


def test_autocorr_shrink_floor_binds_on_near_unit_rho():
    # Strictly increasing series → rho near 1; raw sqrt((1-rho)/(1+rho)) → 0.
    returns = np.linspace(0.01, 0.50, 40)
    rho, factor = kelly._autocorr_shrink(returns)
    assert rho > 0.9
    assert factor == pytest.approx(kelly._AUTOCORR_SHRINK_FLOOR)
    assert 0.0 < factor <= 1.0
