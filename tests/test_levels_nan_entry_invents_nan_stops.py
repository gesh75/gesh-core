"""NaN entry_price is truthy and ``NaN <= 0`` is False — levels invent NaN stops.

Zero/negative/None entry is already pinned as a no-op. A pandas/SQL NaN fill
price is a different IEEE-754 trap: ``_derive_levels`` walks the flat ladder
and writes ``round(nan * 0.95)`` so the close-scan thinks a stop exists.
"""

from __future__ import annotations

import math

from gesh_core.trading import levels


def test_derive_levels_nan_entry_invents_nan_flat_stops() -> None:
    stop, target = levels._derive_levels(
        "BUY", float("nan"), None, None, atr_value=None, symbol=None
    )
    assert stop is not None and math.isnan(stop)
    assert target is not None and math.isnan(target)


def test_derive_levels_nan_entry_with_atr_still_nan() -> None:
    stop, target = levels._derive_levels(
        "BUY", float("nan"), None, None, atr_value=2.0, symbol=None
    )
    assert stop is not None and math.isnan(stop)
    assert target is not None and math.isnan(target)


def test_atr_levels_nan_entry_returns_nan_pair() -> None:
    stop, target = levels._atr_levels("BUY", float("nan"), 2.0)
    assert stop is not None and math.isnan(stop)
    assert target is not None and math.isnan(target)
