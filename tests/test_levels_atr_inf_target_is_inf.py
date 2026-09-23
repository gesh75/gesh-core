"""+inf ATR clamps the stop to MAX_STOP_PCT but leaves take-profit at +inf."""

from __future__ import annotations

import math

from gesh_core.trading import levels


def test_inf_atr_stop_clamps_target_stays_inf():
    stop, target = levels._atr_levels("BUY", 100.0, float("inf"))
    assert stop == 85.0  # 100 - 15% MAX_STOP_PCT
    assert target is not None and math.isinf(target) and target > 0
