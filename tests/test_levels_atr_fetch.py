"""_fetch_atr now uses the shared gesh_core.market_fetch.fetch_ohlcv (reliable
yf.download + RH fallback) instead of the old consensus / Ticker.history path that
intermittently 401'd on a '2mo' period and silently degraded ATR stops to flat.
Network-free via a mocked fetch_ohlcv.
"""
from __future__ import annotations

import numpy as np

import gesh_core.market_fetch as market_fetch
from gesh_core.trading import levels


def _arrays(n=40):
    base = np.linspace(100, 120, n)
    return {"high": base + 2, "low": base - 2, "close": base, "volume": np.full(n, 1_000.0)}


def test_fetch_atr_uses_market_fetch(monkeypatch):
    levels._ATR_CACHE.clear()
    calls = {"n": 0}

    def fake(symbol, period_days=252):
        calls["n"] += 1
        return _arrays()

    monkeypatch.setattr(market_fetch, "fetch_ohlcv", fake)
    a = levels._fetch_atr("XYZ")
    assert calls["n"] == 1
    assert a is not None and a > 0


def test_fetch_atr_none_when_fetch_empty(monkeypatch):
    levels._ATR_CACHE.clear()
    calls = {"n": 0}
    monkeypatch.setattr(
        market_fetch,
        "fetch_ohlcv",
        lambda s, **k: (calls.__setitem__("n", calls["n"] + 1), None)[1],
    )
    assert levels._fetch_atr("XYZ") is None
    assert levels._fetch_atr("XYZ") is None
    assert calls["n"] == 1


def test_fetch_atr_none_on_thin_bars(monkeypatch):
    levels._ATR_CACHE.clear()
    monkeypatch.setattr(market_fetch, "fetch_ohlcv", lambda s, **k: _arrays(5))
    assert levels._fetch_atr("XYZ") is None


def test_fetch_atr_cached_per_day(monkeypatch):
    levels._ATR_CACHE.clear()
    calls = {"n": 0}
    monkeypatch.setattr(market_fetch, "fetch_ohlcv",
                        lambda s, **k: (calls.__setitem__("n", calls["n"] + 1), _arrays())[1])
    levels._fetch_atr("XYZ")
    levels._fetch_atr("XYZ")   # second call served from the per-day cache
    assert calls["n"] == 1


def test_fetch_atr_rejects_invalid_symbol_without_fetch(monkeypatch):
    levels._ATR_CACHE.clear()
    calls = {"n": 0}
    monkeypatch.setattr(
        market_fetch,
        "fetch_ohlcv",
        lambda s, **k: calls.__setitem__("n", calls["n"] + 1),
    )

    assert levels._fetch_atr("X" * 33) is None
    assert levels._fetch_atr("BAD SYMBOL") is None
    assert calls["n"] == 0


def test_atr_cache_size_is_bounded():
    levels._ATR_CACHE.clear()
    for index in range(levels._ATR_CACHE_MAX_SIZE + 1):
        levels._cache_atr((f"SYM{index}", "2026-08-04"), None)

    assert len(levels._ATR_CACHE) == levels._ATR_CACHE_MAX_SIZE
    assert ("SYM0", "2026-08-04") not in levels._ATR_CACHE


def test_fetch_atr_none_when_atr_computes_none(monkeypatch):
    # Flat bars → indicators.atr returns None → must cache the miss, not retry.
    levels._ATR_CACHE.clear()
    calls = {"n": 0}
    flat = np.full(40, 10.0)

    def fake(symbol, period_days=252):
        calls["n"] += 1
        return {"high": flat, "low": flat, "close": flat, "volume": np.full(40, 1_000.0)}

    monkeypatch.setattr(market_fetch, "fetch_ohlcv", fake)
    assert levels._fetch_atr("FLAT") is None
    assert levels._fetch_atr("FLAT") is None
    assert calls["n"] == 1


def test_fetch_atr_none_on_provider_exception(monkeypatch):
    levels._ATR_CACHE.clear()
    calls = {"n": 0}

    def boom(symbol, period_days=252):
        calls["n"] += 1
        raise RuntimeError("401 crumb")

    monkeypatch.setattr(market_fetch, "fetch_ohlcv", boom)
    assert levels._fetch_atr("XYZ") is None
    assert levels._fetch_atr("XYZ") is None
    assert calls["n"] == 1


def test_derive_levels_unusable_entry_preserves_explicit():
    assert levels._derive_levels("BUY", 0.0, 90.0, 110.0) == (90.0, 110.0)
    assert levels._derive_levels("BUY", -5.0, None, None) == (None, None)


def test_derive_levels_lazy_fetch_fills_gaps(monkeypatch):
    levels._ATR_CACHE.clear()
    monkeypatch.setattr(market_fetch, "fetch_ohlcv", lambda s, **k: _arrays())
    stop, target = levels._derive_levels("BUY", 100.0, None, None, symbol="XYZ")
    assert stop is not None and target is not None
    assert stop < 100.0 < target
    # Must not have fallen through to the flat 5/12 ladder.
    assert (stop, target) != (95.0, 112.0)


def test_derive_levels_fetch_miss_falls_back_to_flat(monkeypatch):
    levels._ATR_CACHE.clear()
    monkeypatch.setattr(levels, "_fetch_atr", lambda s: None)
    stop, target = levels._derive_levels("BUY", 100.0, None, None, symbol="XYZ")
    assert (stop, target) == (95.0, 112.0)
