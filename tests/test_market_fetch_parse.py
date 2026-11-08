"""Fail-closed parse / crumb-recovery paths in market_fetch.

Happy-path retry, RH fallback, and SPY open-boundary cache live in
test_market_fetch.py (and open PR #42). These pin the remaining branches that
otherwise crash a consensus run or keep serving a poisoned Yahoo crumb.
"""
from __future__ import annotations

import yfinance.data as yf_data

from gesh_core import market_fetch as mf


class _Unparseable:
    """Looks long enough to pass the row-count guard, then blows up on Close."""

    def __len__(self) -> int:
        return 80

    def __getitem__(self, key):
        raise KeyError(key)


def test_crumb_401_clears_yfinance_crumb_cache(monkeypatch):
    monkeypatch.setattr(mf.time, "sleep", lambda *a, **k: None)
    yf_data._CRUMB = "stale-crumb"

    def always_401(*_a, **_k):
        raise RuntimeError("401 Invalid Crumb")

    monkeypatch.setattr(mf.yf, "download", always_401)
    assert mf.yf_download_with_retry("NVDA", period="1y") is None
    assert yf_data._CRUMB is None


def test_fetch_ohlcv_parse_error_returns_none(monkeypatch):
    monkeypatch.setattr(mf, "yf_download_with_retry", lambda *a, **k: _Unparseable())
    assert mf.fetch_ohlcv("NVDA") is None


def test_fetch_spy_close_parse_error_returns_none(monkeypatch):
    mf._SPY_CACHE.clear()
    monkeypatch.setattr(mf, "yf_download_with_retry", lambda *a, **k: _Unparseable())
    assert mf.fetch_spy_close() is None
    assert "close" not in mf._SPY_CACHE


def test_crossed_market_open_fails_open_on_bad_timestamps():
    # Guard must never raise into fetch_spy_close — a bad clock/zoneinfo
    # should keep the cached array rather than abort the RS node.
    assert mf._crossed_market_open("not-a-ts", "also-bad") is False
