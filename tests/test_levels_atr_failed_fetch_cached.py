"""A failed ATR fetch is cached for the UTC day and not retried.

``_fetch_atr`` stores ``None`` on thin/failed Yahoo so a bad symbol cannot
burn retry quota on every close-scan tick. A later miss of that cache would
re-amplify provider calls under the autopilot's parallel load.
"""

from __future__ import annotations

import pytest

from gesh_core.trading import levels


@pytest.fixture(autouse=True)
def _clear_atr_cache():
    levels._ATR_CACHE.clear()
    yield
    levels._ATR_CACHE.clear()


def test_failed_atr_fetch_is_cached_and_not_refetched(monkeypatch):
    calls: list[str] = []

    def _none(symbol: str, period_days: int = 60):
        calls.append(symbol)
        return None

    monkeypatch.setattr("gesh_core.market_fetch.fetch_ohlcv", _none)
    assert levels.EQUITY_USE_ATR_STOPS is True
    assert levels._fetch_atr("NVDA") is None
    assert levels._fetch_atr("NVDA") is None
    assert calls == ["NVDA"]
    assert any(key[0] == "NVDA" and value is None for key, value in levels._ATR_CACHE.items())


def test_raised_atr_fetch_is_also_cached(monkeypatch):
    calls = {"n": 0}

    def _boom(symbol: str, period_days: int = 60):
        calls["n"] += 1
        raise RuntimeError("401 Invalid Crumb")

    monkeypatch.setattr("gesh_core.market_fetch.fetch_ohlcv", _boom)
    assert levels._fetch_atr("HOOD") is None
    assert levels._fetch_atr("HOOD") is None
    assert calls["n"] == 1
