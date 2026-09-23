"""NaN ATR is truthy: the stop clamps to MIN_STOP_PCT while take-profit stays NaN."""

from __future__ import annotations

import math

from gesh_core.trading import levels


def test_nan_atr_clamps_stop_and_emits_nan_target():
    stop, target = levels._atr_levels("BUY", 100.0, float("nan"))
    # max(lo, min(3*NaN, hi)) → lo because NaN comparisons are False.
    assert stop == 97.0
    assert target is not None and math.isnan(target)
