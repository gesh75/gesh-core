"""NaN ATR fills a numeric stop and a NaN target, so the flat 12% TP never applies."""

from __future__ import annotations

import math

from gesh_core.trading import levels


def test_nan_atr_blocks_flat_target_fill(monkeypatch):
    monkeypatch.setattr(levels, "EQUITY_USE_ATR_STOPS", True)
    stop, target = levels._derive_levels(
        "BUY",
        100.0,
        None,
        None,
        atr_value=float("nan"),
        symbol=None,
    )
    assert stop == 97.0
    assert target is not None and math.isnan(target)
