"""Tests for gesh_core.market_fetch (consensus Phase 1).

Fully network-free: yf.download is monkeypatched and the Robinhood fallback's
price_source is stubbed into sys.modules. time.sleep is no-op'd so retry paths
don't actually wait.
"""
from __future__ import annotations

import sys
import types

import numpy as np
import pandas as pd
import pytest

from gesh_core import market_fetch as mf


def _df(n=260):
    return pd.DataFrame({
        "Close":  np.linspace(100, 130, n),
        "High":   np.linspace(101, 131, n),
        "Low":    np.linspace(99, 129, n),
        "Volume": np.linspace(1e6, 2e6, n),
    })


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(mf.time, "sleep", lambda *a, **k: None)
    mf._SPY_CACHE.clear()
    yield
    mf._SPY_CACHE.clear()


def test_module_loads_from_gesh_core():
    assert "gesh_core" in (mf.__file__ or "")
    # underscore aliases match the engine's import sites
    assert mf._yf_download_with_retry is mf.yf_download_with_retry
    assert mf._fetch_ohlcv is mf.fetch_ohlcv


def test_download_success(monkeypatch):
    monkeypatch.setattr(mf.yf, "download", lambda *a, **k: _df())
    out = mf.yf_download_with_retry("NVDA", period="2y")
    assert out is not None and len(out) == 260


def test_download_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}
    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("401 Invalid Crumb")
        return _df()
    monkeypatch.setattr(mf.yf, "download", flaky)
    out = mf.yf_download_with_retry("NVDA", period="2y")
    assert out is not None and calls["n"] == 3   # retried twice then ok


def test_download_robinhood_fallback(monkeypatch):
    # Yahoo always fails -> lazy `import price_source` must provide the data.
    monkeypatch.setattr(mf.yf, "download", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crumb")))
    stub = types.ModuleType("price_source")
    stub.rh_fallback = lambda symbol, **k: _df(30)
    monkeypatch.setitem(sys.modules, "price_source", stub)
    out = mf.yf_download_with_retry("NVDA", period="2y")
    assert out is not None and len(out) == 30


def test_download_all_fail_returns_none(monkeypatch):
    monkeypatch.setattr(mf.yf, "download", lambda *a, **k: pd.DataFrame())   # empty
    monkeypatch.setitem(sys.modules, "price_source", types.ModuleType("price_source"))  # no rh_fallback
    assert mf.yf_download_with_retry("ZZZZ", period="2y") is None


def test_fetch_ohlcv_returns_arrays(monkeypatch):
    monkeypatch.setattr(mf, "yf_download_with_retry", lambda *a, **k: _df(252))
    out = mf.fetch_ohlcv("NVDA")
    assert set(out) == {"close", "high", "low", "volume"}
    assert isinstance(out["close"], np.ndarray) and len(out["close"]) == 252
    assert out["close"][0] == pytest.approx(100.0)


def test_fetch_ohlcv_thin_data_returns_none(monkeypatch):
    monkeypatch.setattr(mf, "yf_download_with_retry", lambda *a, **k: _df(10))
    assert mf.fetch_ohlcv("NVDA") is None


def test_fetch_spy_close_caches(monkeypatch):
    calls = {"n": 0}
    def dl(*a, **k):
        calls["n"] += 1
        return _df(60)
    monkeypatch.setattr(mf, "yf_download_with_retry", dl)
    a = mf.fetch_spy_close()
    b = mf.fetch_spy_close()
    assert a is not None and np.array_equal(a, b)
    assert calls["n"] == 1   # second call served from the 30-min TTL cache


def test_fetch_ohlcv_nan_rows_stay_aligned(monkeypatch):
    # A NaN in ONE column must drop the whole row for ALL columns — per-column
    # dropna silently misaligned close[i]/volume[i] pairs downstream.
    df = _df(60)
    df.loc[10, "Volume"] = np.nan
    df.loc[20, "High"] = np.nan
    monkeypatch.setattr(mf, "yf_download_with_retry", lambda *a, **k: df)
    out = mf.fetch_ohlcv("NVDA")
    assert out is not None
    lengths = {k: len(v) for k, v in out.items()}
    assert len(set(lengths.values())) == 1, lengths        # all arrays same length
    assert lengths["close"] == 58                          # both NaN rows dropped
    # Row pairing preserved: index 10's row is gone from every array.
    assert float(df.loc[11, "Close"]) in out["close"]
    assert float(df.loc[10, "Close"]) not in out["close"]
