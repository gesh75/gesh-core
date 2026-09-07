"""A first-bar ``-100%`` return makes ``_max_drawdown`` non-finite.

Drawdown divides by ``running_max``. When the first return is ``-1.0``,
cumulative equity is 0 and the ratio is ``0/0`` → NaN. That NaN is then
``round``ed into ``kelly_size_holding``'s ``max_drawdown`` field. A later
halt/delisting-style bar after a gain is a finite ``-100%`` — only the
zero running-max path is the JSON hazard. Pin both.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from gesh_core.kelly import MIN_HISTORY_DAYS, _max_drawdown, kelly_size_holding


def test_opening_terminal_loss_is_nan() -> None:
    returns = np.array([-1.0] + [0.01] * (MIN_HISTORY_DAYS - 1), dtype=float)
    mdd = _max_drawdown(returns)
    assert not math.isfinite(mdd)


def test_later_terminal_loss_is_finite_minus_100() -> None:
    returns = np.array([0.05, -1.0] + [0.0] * (MIN_HISTORY_DAYS - 2), dtype=float)
    assert _max_drawdown(returns) == pytest.approx(-100.0)


def test_size_holding_surfaces_nonfinite_max_drawdown() -> None:
    returns = np.array([-1.0] + [0.01] * (MIN_HISTORY_DAYS + 10), dtype=float)
    res = kelly_size_holding("X", 1_000, 100_000, 10, 12, returns=returns)
    assert "error" not in res
    assert "optimal_pct" in res
    assert "action" in res
    assert not math.isfinite(res["max_drawdown"])
