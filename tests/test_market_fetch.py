"""Tests for gesh_core.market_fetch (consensus Phase 1).

Fully network-free: yf.download and the explicitly injected Robinhood fallback are
stubbed. time.sleep is no-op'd so retry paths don't actually wait.
"""
from __future__ import annotations

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
    # Yahoo always fails -> the explicitly trusted host callback provides the data.
    monkeypatch.setattr(mf.yf, "download", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crumb")))
    out = mf.yf_download_with_retry(
        "NVDA", period="2y", fallback=lambda symbol, **k: _df(30)
    )
    assert out is not None and len(out) == 30


def test_download_all_fail_returns_none(monkeypatch):
    monkeypatch.setattr(mf.yf, "download", lambda *a, **k: pd.DataFrame())   # empty
    assert mf.yf_download_with_retry("ZZZZ", period="2y") is None


def test_yf_download_fallback_exception_returns_none(monkeypatch):
    monkeypatch.setattr(mf.yf, "download", lambda *a, **k: pd.DataFrame())

    def boom(*_a, **_k):
        raise RuntimeError("rh down")

    assert mf.yf_download_with_retry("NVDA", period="2y", fallback=boom) is None


def test_download_does_not_import_untrusted_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(mf.yf, "download", lambda *a, **k: pd.DataFrame())
    marker = tmp_path / "imported"
    (tmp_path / "price_source.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
    )
    monkeypatch.syspath_prepend(tmp_path)

    assert mf.yf_download_with_retry("ZZZZ", period="2y") is None
    assert not marker.exists()


def test_fetch_ohlcv_period_days_over_260_requests_two_year(monkeypatch):
    seen: dict[str, object] = {}

    def capture(_symbol, **kwargs):
        seen.clear()
        seen.update(kwargs)
        return _df(300)

    monkeypatch.setattr(mf, "yf_download_with_retry", capture)
    assert mf.fetch_ohlcv("NVDA", period_days=300) is not None
    assert seen["period"] == "2y"
    assert mf.fetch_ohlcv("NVDA", period_days=252) is not None
    assert seen["period"] == "1y"


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


# ─── open-boundary SPY cache invalidation (audit: RS window alignment) ────────

def _et_ts(hour: int, minute: int) -> float:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime(2026, 7, 2, hour, minute, tzinfo=ZoneInfo("America/New_York")).timestamp()


def test_crossed_market_open_pre_to_post():
    from gesh_core.market_fetch import _crossed_market_open
    assert _crossed_market_open(_et_ts(9, 25), _et_ts(9, 35)) is True   # spans 09:30


def test_not_crossed_within_session_or_pre_open():
    from gesh_core.market_fetch import _crossed_market_open
    assert _crossed_market_open(_et_ts(10, 0), _et_ts(10, 20)) is False   # both post-open
    assert _crossed_market_open(_et_ts(9, 0), _et_ts(9, 20)) is False     # both pre-open


def test_spy_cache_invalidated_across_open(monkeypatch):
    """A pre-open cached SPY array must NOT be served post-open — it lacks
    today's bar while symbol fetches carry it (one-session RS window offset)."""
    import numpy as np

    from gesh_core import market_fetch as mf

    calls = {"n": 0}

    def fake_fetch(*a, **k):
        calls["n"] += 1
        import pandas as pd
        idx = pd.date_range("2026-01-01", periods=40)
        return pd.DataFrame({"Close": np.linspace(100, 110, 40)}, index=idx)

    monkeypatch.setattr(mf, "yf_download_with_retry", fake_fetch)
    monkeypatch.setattr(mf, "_SPY_CACHE", {})

    monkeypatch.setattr(mf.time, "time", lambda: _et_ts(9, 25))
    assert mf.fetch_spy_close() is not None
    assert calls["n"] == 1

    monkeypatch.setattr(mf.time, "time", lambda: _et_ts(9, 35))   # crossed 09:30
    assert mf.fetch_spy_close() is not None
    assert calls["n"] == 2, "pre-open cache must be refetched after the open"

    monkeypatch.setattr(mf.time, "time", lambda: _et_ts(9, 45))   # same session
    assert mf.fetch_spy_close() is not None
    assert calls["n"] == 2, "post-open cache serves normally within TTL"
