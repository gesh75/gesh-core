"""_fetch_atr rejects empty, whitespace, and overlong symbols before any network.

The ASCII ticker regex is the only host-side guard that keeps garbage
symbols off Yahoo. A miss must return None and must not call fetch_ohlcv
(or populate the per-day cache).
"""

from __future__ import annotations

import pytest

from gesh_core.trading import levels


@pytest.fixture(autouse=True)
def _clear_atr_cache():
    levels._ATR_CACHE.clear()
    yield
    levels._ATR_CACHE.clear()


@pytest.mark.parametrize("symbol", ["", " ", "  NVDA", "A" * 40, "n v d a"])
def test_unusable_symbols_never_hit_market_fetch(monkeypatch, symbol):
    called: list[str] = []

    def boom(sym: str, period_days: int = 60):
        called.append(sym)
        raise AssertionError("fetch_ohlcv must not run for a rejected symbol")

    monkeypatch.setattr("gesh_core.market_fetch.fetch_ohlcv", boom)
    assert levels._fetch_atr(symbol) is None
    assert called == []
    assert levels._ATR_CACHE == {}
