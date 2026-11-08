"""ATR period edges the default-14 suite never hits.

``EQUITY_ATR_PERIOD`` is env-overridable. period=1 is a legal Wilder window
(seed = the single TR, no smoothing loop). period=0 currently divides by
zero in the smoother — ``_fetch_atr`` swallows that, but the pure helper
does not. Pin both so a later fail-closed change is reviewable.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.indicators import atr


def test_period_one_returns_the_single_true_range() -> None:
    # Two bars → one TR. high-low = 2, gap vs prior close = 2.
    high, low, close = [11.0, 12.0], [9.0, 10.0], [10.0, 11.0]
    value = atr(high, low, close, period=1)
    assert value == 2.0


def test_period_one_still_needs_two_bars() -> None:
    assert atr([11.0], [9.0], [10.0], period=1) is None


@pytest.mark.filterwarnings("ignore:Mean of empty slice")
@pytest.mark.filterwarnings("ignore:invalid value encountered in scalar divide")
def test_period_zero_raises_zero_division() -> None:
    high = [11.0, 12.0, 13.0]
    low = [9.0, 10.0, 11.0]
    close = [10.0, 11.0, 12.0]
    with pytest.raises(ZeroDivisionError):
        atr(high, low, close, period=0)


def test_period_one_flat_range_is_none() -> None:
    flat = [10.0, 10.0]
    assert atr(flat, flat, flat, period=1) is None


def test_low_length_mismatch_returns_none() -> None:
    high, low, close = [11.0, 12.0, 13.0], [9.0, 10.0], [10.0, 11.0, 12.0]
    assert atr(high, low, close, period=1) is None
