"""Network-free tests for kelly._fetch_returns fail-closed + date alignment.

Sizing math is already covered via injected returns. The fetch path is what
silently skips a name (None) or mis-aligns correlation haircuts when Yahoo
401s, history is thin, or tz-aware / duplicate indexes are left raw.
"""
from __future__ import annotations

import sys
from types import ModuleType

import pandas as pd
import pytest

from gesh_core import kelly


class _FakeTicker:
    def __init__(self, frame: pd.DataFrame | None = None, *, error: Exception | None = None):
        self._frame = frame
        self._error = error

    def history(self, **_kwargs):
        if self._error is not None:
            raise self._error
        return self._frame


def _ohlc(closes, *, tz: str | None = None, freq: str = "D") -> pd.DataFrame:
    idx = pd.date_range("2026-01-02", periods=len(closes), freq=freq)
    if tz:
        idx = idx.tz_localize(tz)
    return pd.DataFrame({"Close": closes}, index=idx)


def _install_price_source(monkeypatch, frame: pd.DataFrame | None, *, explode: bool = False):
    mod = ModuleType("price_source")

    def rh_fallback(symbol, **_kwargs):
        if explode:
            raise RuntimeError("rh down")
        return frame

    mod.rh_fallback = rh_fallback  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "price_source", mod)


def test_yahoo_exception_uses_robinhood_fallback(monkeypatch):
    closes = [100.0 + i * 0.1 for i in range(40)]
    fallback = _ohlc(closes)
    monkeypatch.setattr(kelly.yf, "Ticker", lambda _s: _FakeTicker(error=RuntimeError("401 crumb")))
    _install_price_source(monkeypatch, fallback)

    series = kelly._fetch_returns("NVDA", days=90)
    assert series is not None
    assert series.index.tz is None
    assert series.index.is_monotonic_increasing


def test_empty_yahoo_uses_robinhood_fallback(monkeypatch):
    closes = [50.0 + i * 0.2 for i in range(40)]
    monkeypatch.setattr(kelly.yf, "Ticker", lambda _s: _FakeTicker(pd.DataFrame()))
    _install_price_source(monkeypatch, _ohlc(closes))

    series = kelly._fetch_returns("AMD")
    assert series is not None
    assert len(series) >= kelly.MIN_HISTORY_DAYS - 1  # pct_change drops one row


def test_both_sources_empty_returns_none(monkeypatch):
    monkeypatch.setattr(kelly.yf, "Ticker", lambda _s: _FakeTicker(pd.DataFrame()))
    _install_price_source(monkeypatch, pd.DataFrame())
    assert kelly._fetch_returns("ZZZ") is None


def test_missing_price_source_after_yahoo_fail_returns_none(monkeypatch):
    monkeypatch.setattr(kelly.yf, "Ticker", lambda _s: _FakeTicker(error=RuntimeError("crumb")))
    monkeypatch.setitem(sys.modules, "price_source", None)  # force ImportError
    # A missing host module must not raise into the daily chain.
    assert kelly._fetch_returns("HOOD") is None


def test_thin_history_returns_none(monkeypatch):
    thin = _ohlc([10.0, 10.1, 10.2])  # well under MIN_HISTORY_DAYS
    monkeypatch.setattr(kelly.yf, "Ticker", lambda _s: _FakeTicker(thin))
    assert kelly._fetch_returns("TINY") is None


def test_tz_aware_index_is_stripped_and_normalized(monkeypatch):
    closes = [100.0 + i for i in range(40)]
    frame = _ohlc(closes, tz="America/New_York")
    # Afternoon stamps must collapse to the calendar date, else an inner join
    # against a naive RH series matches ZERO days and the haircut fails open.
    frame.index = frame.index + pd.Timedelta(hours=16)
    monkeypatch.setattr(kelly.yf, "Ticker", lambda _s: _FakeTicker(frame))

    series = kelly._fetch_returns("MSFT")
    assert series is not None
    assert series.index.tz is None
    assert all(ts.hour == 0 and ts.minute == 0 for ts in series.index)


def test_duplicate_dates_keep_last_close(monkeypatch):
    idx = pd.to_datetime(
        ["2026-01-05", "2026-01-06", "2026-01-06"]
        + [f"2026-01-{d:02d}" for d in range(7, 40)]
    )
    # Two prints on Jan 6: keep="last" must retain the 20.0 close's return.
    closes = [10.0, 11.0, 20.0] + [20.0 + i * 0.1 for i in range(len(idx) - 3)]
    frame = pd.DataFrame({"Close": closes}, index=idx)
    monkeypatch.setattr(kelly.yf, "Ticker", lambda _s: _FakeTicker(frame))

    series = kelly._fetch_returns("DUP")
    assert series is not None
    jan6 = series.loc[pd.Timestamp("2026-01-06")]
    assert float(jan6) == pytest.approx(20.0 / 11.0 - 1.0)


def test_outer_exception_returns_none(monkeypatch):
    monkeypatch.setattr(kelly.yf, "Ticker", lambda _s: (_ for _ in ()).throw(RuntimeError("boom")))
    _install_price_source(monkeypatch, None, explode=True)
    assert kelly._fetch_returns("ERR") is None
