"""HOLD currently falls through to the SELL/short flat ladder.

``_derive_levels`` only special-cases BUY; every other action — including
HOLD — gets the inverted 5%/12% short levels. That is load-bearing for any
caller that derives levels before checking action. Pin it so a later
BUY/SELL-only rewrite cannot silently leave HOLD positions without exits
(or invent long levels on a short book).
"""
from __future__ import annotations

from gesh_core.trading import levels


def test_hold_flat_defaults_match_sell_ladder() -> None:
    hold = levels._derive_levels("HOLD", 100.0, None, None, atr_value=None, symbol=None)
    sell = levels._derive_levels("SELL", 100.0, None, None, atr_value=None, symbol=None)
    assert hold == sell == (105.0, 88.0)


def test_hold_preserves_explicit_levels() -> None:
    stop, target = levels._derive_levels("HOLD", 100.0, 90.0, 130.0)
    assert (stop, target) == (90.0, 130.0)
