"""Whitespace-only TradeIntent symbols currently pass validate().

``validate()`` rejects empty / non-ASCII / len>12, but a truthy run of spaces
is ASCII and short, so it is treated as valid. ``manual()`` uppercases without
stripping, so ``" nvda "`` becomes ``" NVDA "`` and likewise passes. Pin the
current contract so a later strip/reject change is reviewable — a broker must
never be asked to trade ``"   "`` by accident, and any tightening must not
silently start rejecting class-share tickers.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.contract import TradeIntent, manual


@pytest.mark.parametrize("symbol", [" ", "   ", "\t", "\n"])
def test_whitespace_only_symbol_currently_passes_validate(symbol):
    problems = TradeIntent(symbol=symbol, action="HOLD", confidence=1.0, source="m").validate()
    assert problems == []


def test_manual_does_not_strip_surrounding_whitespace():
    intent = manual(" nvda ", "BUY", target_position_pct=0.02)
    assert intent.symbol == " NVDA "
    assert intent.validate() == []


def test_internal_space_ticker_passes_and_is_not_collapsed():
    # Contrast: a real space inside a ticker is also currently accepted.
    # A future regex that rejects whitespace-only must not also reject this
    # unless the product explicitly decides class-share spacing is invalid.
    intent = TradeIntent(symbol="BRK B", action="HOLD", confidence=1.0, source="m")
    assert intent.validate() == []
