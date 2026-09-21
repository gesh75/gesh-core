"""Non-positive ATR must not invent adaptive stops.

_atr_levels already rejects a missing ATR; 0.0 and negative values must also
return (None, None) so _derive_levels falls back to the flat ladder instead of
producing a zero-width or inverted stop.
"""

from __future__ import annotations

import pytest

from gesh_core.trading import levels


@pytest.mark.parametrize("atr_value", [0.0, -1.5])
def test_atr_levels_nonpositive_atr_returns_none(atr_value: float):
    assert levels._atr_levels("BUY", 100.0, atr_value) == (None, None)
    assert levels._atr_levels("SELL", 100.0, atr_value) == (None, None)
