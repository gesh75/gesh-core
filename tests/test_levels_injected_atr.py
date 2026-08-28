"""Precomputed ATR must fill missing levels without touching the network.

Production writes pass ``atr_value`` so ``_fetch_atr`` stays off the DB path.
A regression that ignores the injected value would either hit Yahoo on every
fill or silently fall back to the flat 5/12 ladder.
"""

from __future__ import annotations

import pytest

from gesh_core.trading import levels


@pytest.fixture(autouse=True)
def _atr_stops_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(levels, "EQUITY_USE_ATR_STOPS", True)


def test_injected_atr_fills_both_sides_and_skips_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        levels,
        "_fetch_atr",
        lambda symbol: (_ for _ in ()).throw(AssertionError(f"unexpected fetch for {symbol}")),
    )
    stop, target = levels._derive_levels("BUY", 100.0, None, None, symbol="NVDA", atr_value=2.0)
    expected = levels._atr_levels("BUY", 100.0, 2.0)
    assert (stop, target) == expected
    assert stop is not None and target is not None
    assert stop < 100.0 < target


def test_injected_atr_preserves_explicit_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        levels,
        "_fetch_atr",
        lambda symbol: (_ for _ in ()).throw(AssertionError("unexpected fetch")),
    )
    stop, target = levels._derive_levels("BUY", 100.0, 91.0, None, symbol="NVDA", atr_value=2.0)
    assert stop == pytest.approx(91.0)
    assert target == pytest.approx(levels._atr_levels("BUY", 100.0, 2.0)[1])


def test_injected_atr_sell_inverts_and_skips_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        levels,
        "_fetch_atr",
        lambda symbol: (_ for _ in ()).throw(AssertionError("unexpected fetch")),
    )
    stop, target = levels._derive_levels("SELL", 100.0, None, None, symbol="NVDA", atr_value=2.0)
    assert (stop, target) == levels._atr_levels("SELL", 100.0, 2.0)


def test_misconfigured_min_gt_max_still_clamps_to_intended_max(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Env swap MIN=15% / MAX=3% must not let risk exceed the larger bound."""
    monkeypatch.setattr(levels, "EQUITY_MIN_STOP_PCT", 0.15)
    monkeypatch.setattr(levels, "EQUITY_MAX_STOP_PCT", 0.03)
    monkeypatch.setattr(levels, "EQUITY_ATR_STOP_MULT", 3.0)
    monkeypatch.setattr(levels, "EQUITY_ATR_TARGET_MULT", 5.0)
    # 3×ATR = 30 on a $100 name would be 30% without the ordered clamp.
    stop, target = levels._atr_levels("BUY", 100.0, 10.0)
    assert stop is not None and target is not None
    risk = 100.0 - stop
    assert risk == pytest.approx(15.0)  # max(3, 15) percent of entry
    assert target == pytest.approx(150.0)  # 5×ATR is independent of the clamp
