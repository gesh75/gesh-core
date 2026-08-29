"""Invalid entry prices must not invent stops or targets.

Broker/paper fills of 0 or negative must leave levels untouched so the EOD
sweep cannot fire on a fabricated ladder.
"""

from __future__ import annotations

from gesh_core.trading import levels


def test_derive_levels_zero_entry_leaves_gaps():
    assert levels._derive_levels("BUY", 0.0, None, None) == (None, None)


def test_derive_levels_negative_entry_preserves_explicit():
    assert levels._derive_levels("BUY", -5.0, 90.0, 110.0) == (90.0, 110.0)


def test_derive_levels_zero_entry_ignores_injected_atr():
    assert levels._derive_levels("SELL", 0.0, None, None, atr_value=2.0) == (None, None)


def test_derive_levels_none_entry_preserves_explicit():
    assert levels._derive_levels("BUY", None, 95.0, 112.0) == (95.0, 112.0)  # type: ignore[arg-type]
