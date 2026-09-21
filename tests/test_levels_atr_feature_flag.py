"""EQUITY_USE_ATR_STOPS=0 is the kill switch for network-bound stop derivation.

A regression that still fetches under the flag adds latency on the DB-write path
and can silently change stops when the provider flakes.
"""
from __future__ import annotations

import gesh_core.market_fetch as market_fetch
from gesh_core.trading import levels


def test_fetch_atr_disabled_skips_market_fetch(monkeypatch):
    levels._ATR_CACHE.clear()
    monkeypatch.setattr(levels, "EQUITY_USE_ATR_STOPS", False)
    calls = {"n": 0}
    monkeypatch.setattr(
        market_fetch,
        "fetch_ohlcv",
        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1),
    )

    assert levels._fetch_atr("NVDA") is None
    assert calls["n"] == 0


def test_fetch_atr_rejects_non_string_without_fetch(monkeypatch):
    levels._ATR_CACHE.clear()
    monkeypatch.setattr(levels, "EQUITY_USE_ATR_STOPS", True)
    calls = {"n": 0}
    monkeypatch.setattr(
        market_fetch,
        "fetch_ohlcv",
        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1),
    )

    assert levels._fetch_atr(None) is None  # type: ignore[arg-type]
    assert levels._fetch_atr(123) is None  # type: ignore[arg-type]
    assert calls["n"] == 0


def test_derive_levels_uses_flat_defaults_when_atr_disabled(monkeypatch):
    monkeypatch.setattr(levels, "EQUITY_USE_ATR_STOPS", False)
    # Injected ATR would otherwise widen the stop; the flag must ignore it.
    stop, target = levels._derive_levels(
        "BUY", 100.0, None, None, symbol="NVDA", atr_value=10.0
    )
    assert stop == 95.0
    assert target == 112.0
