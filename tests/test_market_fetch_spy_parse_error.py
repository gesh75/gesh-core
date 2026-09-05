"""A SPY frame missing Close must return None and must not be cached.

A parse failure that wrote the cache would serve a poisoned RS benchmark
for the rest of the 30-min TTL.
"""
from __future__ import annotations

import pandas as pd
import pytest

from gesh_core import market_fetch as mf


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(mf.time, "sleep", lambda *a, **k: None)
    mf._SPY_CACHE.clear()
    yield
    mf._SPY_CACHE.clear()


def test_spy_missing_close_returns_none_and_does_not_cache(monkeypatch):
    calls = {"n": 0}

    def no_close(*_a, **_k):
        calls["n"] += 1
        return pd.DataFrame({"Open": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})

    monkeypatch.setattr(mf, "yf_download_with_retry", no_close)
    assert mf.fetch_spy_close() is None
    assert mf.fetch_spy_close() is None
    assert calls["n"] == 2
    assert "close" not in mf._SPY_CACHE
