"""Unknown / ADD / TRIM / EXECUTE actions use the SELL (inverted) flat ladder.

``_derive_levels`` only special-cases BUY. Everything else — including ADD,
which is an entry — falls into the SELL branch (stop above, target below).
Pin that so a later action-aware ladder cannot silently invert stops.
"""

from __future__ import annotations

import pytest

from gesh_core.trading import levels


@pytest.mark.parametrize("action", ["ADD", "TRIM", "EXECUTE"])
def test_non_buy_actions_use_inverted_flat_ladder(action):
    stop, target = levels._derive_levels(action, 100.0, None, None, atr_value=None, symbol=None)
    assert stop == 105.0
    assert target == 88.0


def test_buy_still_uses_long_flat_ladder():
    stop, target = levels._derive_levels("BUY", 100.0, None, None, atr_value=None, symbol=None)
    assert stop == 95.0
    assert target == 112.0
