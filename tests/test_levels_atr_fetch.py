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
    monkeypatch.setattr(market_fetch, "fetch_ohlcv", lambda s, **k: None)
    assert levels._fetch_atr("XYZ") is None


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
