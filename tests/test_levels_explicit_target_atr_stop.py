"""Injected ATR must fill a missing stop while preserving an explicit target.

The sibling path (explicit stop, ATR-filled target) is covered on an open
coverage PR. The inverse is the production write that already has a take-
profit from the intent and must still attach a protective stop from
precomputed ATR — without hitting the network or overwriting the target.
"""
from __future__ import annotations

import pytest

from gesh_core.trading import levels


@pytest.fixture(autouse=True)
def _atr_stops_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(levels, "EQUITY_USE_ATR_STOPS", True)


def test_injected_atr_fills_stop_and_preserves_explicit_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        levels,
        "_fetch_atr",
        lambda symbol: (_ for _ in ()).throw(AssertionError(f"unexpected fetch for {symbol}")),
    )
    stop, target = levels._derive_levels(
        "BUY", 100.0, None, 130.0, symbol="NVDA", atr_value=2.0
    )
    expected_stop, _ = levels._atr_levels("BUY", 100.0, 2.0)
    assert stop == pytest.approx(expected_stop)
    assert target == pytest.approx(130.0)


def test_injected_atr_fills_stop_on_sell_and_preserves_explicit_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        levels,
        "_fetch_atr",
        lambda symbol: (_ for _ in ()).throw(AssertionError("unexpected fetch")),
    )
    stop, target = levels._derive_levels(
        "SELL", 100.0, None, 80.0, symbol="NVDA", atr_value=2.0
    )
    expected_stop, _ = levels._atr_levels("SELL", 100.0, 2.0)
    assert stop == pytest.approx(expected_stop)
    assert target == pytest.approx(80.0)
