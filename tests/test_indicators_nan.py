"""ATR must fail closed on non-finite OHLC — never feed NaN into stops.

Bad Yahoo/Robinhood bars must return None so `_derive_levels` falls back to the
flat 5/12 ladder instead of writing a NaN stop that the EOD sweep cannot match.
"""

from __future__ import annotations

import math

import pytest

from gesh_core.trading.indicators import atr


def _trending(
    n: int = 30, start: float = 100.0, step: float = 1.0
) -> tuple[list[float], list[float], list[float]]:
    high, low, close = [], [], []
    price = start
    for _ in range(n):
        high.append(price + 1.0)
        low.append(price - 1.0)
        close.append(price)
        price += step
    return high, low, close


@pytest.mark.parametrize(
    "field,value",
    [
        ("close", float("nan")),
        ("high", float("inf")),
        ("low", float("-inf")),
    ],
)
def test_atr_returns_none_on_non_finite_bar(field: str, value: float):
    high, low, close = _trending(30)
    series = {"high": high, "low": low, "close": close}
    series[field][10] = value
    assert atr(series["high"], series["low"], series["close"], period=14) is None


def test_atr_still_finite_on_clean_trend():
    high, low, close = _trending(40)
    value = atr(high, low, close, period=14)
    assert value is not None
    assert math.isfinite(value)
    assert value > 0
