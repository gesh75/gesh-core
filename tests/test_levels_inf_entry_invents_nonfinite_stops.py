"""+Inf entry is usable (``not inf`` is False, ``inf <= 0`` is False).

The flat ladder then writes inf stops. ``-inf`` still hits ``<= 0`` and
returns the caller's levels unchanged — pin both sides so a sign flip cannot
silently start inventing exits.
"""

from __future__ import annotations

import math

from gesh_core.trading import levels


def test_derive_levels_inf_entry_invents_inf_flat_stops() -> None:
    stop, target = levels._derive_levels(
        "BUY", float("inf"), None, None, atr_value=None, symbol=None
    )
    assert stop == float("inf")
    assert target == float("inf")


def test_derive_levels_neg_inf_entry_does_not_invent() -> None:
    stop, target = levels._derive_levels(
        "BUY", float("-inf"), None, None, atr_value=None, symbol=None
    )
    assert stop is None
    assert target is None


def test_atr_levels_inf_entry_is_nonfinite() -> None:
    stop, target = levels._atr_levels("BUY", float("inf"), 2.0)
    assert stop is not None and (math.isnan(stop) or math.isinf(stop))
    assert target is not None and math.isinf(target)
