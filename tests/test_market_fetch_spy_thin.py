"""Leftover SPY-benchmark fetch edges: thin bars and TTL expiry.

Relative-strength compares each symbol to this cached SPY series. A 4-bar
download must not become a benchmark, and a cache older than 30 minutes must
refetch so a long-lived autopilot process cannot serve a stale window.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gesh_core import market_fetch as mf


def _df(n: int = 60) -> pd.DataFrame:
    return pd.DataFrame({"Close": np.linspace(100, 110, n)})


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(mf.time, "sleep", lambda *a, **k: None)
    mf._SPY_CACHE.clear()
    yield
    mf._SPY_CACHE.clear()


def test_fetch_spy_close_thin_data_returns_none(monkeypatch):
    monkeypatch.setattr(mf, "yf_download_with_retry", lambda *a, **k: _df(4))
    assert mf.fetch_spy_close() is None
    assert "close" not in mf._SPY_CACHE


def test_fetch_spy_close_none_download_returns_none(monkeypatch):
    monkeypatch.setattr(mf, "yf_download_with_retry", lambda *a, **k: None)
    assert mf.fetch_spy_close() is None


def test_fetch_spy_close_ttl_expiry_refetches(monkeypatch):
    calls = {"n": 0}

    def dl(*_a, **_k):
        calls["n"] += 1
        return _df(60)

    clock = {"now": 1_700_000_000.0}
    monkeypatch.setattr(mf, "yf_download_with_retry", dl)
    monkeypatch.setattr(mf.time, "time", lambda: clock["now"])
    monkeypatch.setattr(mf, "_crossed_market_open", lambda *_a, **_k: False)

    first = mf.fetch_spy_close()
    assert first is not None and calls["n"] == 1

    clock["now"] += 29 * 60
    assert mf.fetch_spy_close() is not None
    assert calls["n"] == 1

    clock["now"] += 2 * 60  # past the 30-minute TTL
    assert mf.fetch_spy_close() is not None
    assert calls["n"] == 2
