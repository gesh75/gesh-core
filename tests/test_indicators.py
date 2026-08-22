"""Direct tests for gesh_core.trading.indicators (ATR was only exercised via levels)."""
from __future__ import annotations

import math

from gesh_core.trading.indicators import atr


def _trending(n: int = 30, start: float = 100.0, step: float = 1.0):
    high, low, close = [], [], []
    price = start
    for _ in range(n):
        high.append(price + 1.0)
        low.append(price - 1.0)
        close.append(price)
        price += step
    return high, low, close


def test_atr_returns_none_when_too_short():
    h, lo, c = _trending(10)
    assert atr(h, lo, c, period=14) is None


def test_atr_returns_none_on_length_mismatch():
    h, lo, c = _trending(30)
    assert atr(h[:-1], lo, c) is None


def test_atr_wilder_positive_finite_on_a_trend():
    h, lo, c = _trending(40)
    value = atr(h, lo, c, period=14)
    assert value is not None
    assert math.isfinite(value)
    assert value > 0


def test_atr_none_when_true_range_collapses_to_zero():
    flat = [10.0] * 30
    assert atr(flat, flat, flat, period=14) is None
