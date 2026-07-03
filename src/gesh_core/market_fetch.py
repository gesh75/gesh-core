"""Shared market-data fetch infrastructure (consensus convergence — Phase 1).

The engine's consensus pre-fetches OHLCV ONCE per symbol and slices arrays to each
node (≈3 calls/symbol vs the product's ≈8 self-fetches). This module is the shared
foundation that future product-side consensus convergence builds on — a single,
retry-hardened Yahoo fetch with a Robinhood fallback, so neither repo hand-copies it.

Faithful port of the engine's ``consensus._yf_download_with_retry`` / ``_fetch_ohlcv``
/ ``_fetch_spy_close``. Public names are unprefixed; the ``_``-prefixed aliases match
the engine's existing import sites (``from consensus import _yf_download_with_retry``)
so the engine can adopt this module later with no call-site churn.

Network-bound but fully guarded — every failure path returns ``None`` (never raises).
The Robinhood fallback does a lazy ``import price_source`` resolved against the running
repo's own price_source module (host-provided, like kelly/levels).
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)

_YF_MAX_RETRIES = 3
_YF_BASE_DELAY = 2.0   # seconds base — actual = base * 2^attempt + jitter


def yf_download_with_retry(symbol: str, **kwargs: Any):
    """yf.download() with exponential backoff on 401/crumb errors + Robinhood fallback.

    Accepts the same kwargs as yf.download(). Returns the DataFrame on success, or
    ``None`` after all retries (and the RH fallback) are exhausted. Never raises.
    """
    for attempt in range(_YF_MAX_RETRIES):
        try:
            raw = yf.download(symbol, progress=False, **kwargs)
            if raw is not None and len(raw) >= 5:
                return raw
            if attempt < _YF_MAX_RETRIES - 1:
                time.sleep(_YF_BASE_DELAY + random.uniform(0, 1))
        except Exception as e:  # noqa: BLE001 — fetch is best-effort
            msg = str(e).lower()
            is_crumb = "crumb" in msg or "401" in msg or "unauthorized" in msg
            logger.debug("yf_download attempt %d for %s: %s", attempt + 1, symbol, e)
            if attempt < _YF_MAX_RETRIES - 1:
                delay = _YF_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1.5)
                if is_crumb:
                    try:
                        import yfinance.data as _yfd  # noqa: PLC0415
                        if hasattr(_yfd, "_CRUMB"):
                            _yfd._CRUMB = None  # type: ignore[attr-defined]
                    except Exception:
                        pass
                time.sleep(delay)
            else:
                logger.warning("yf_download: all retries failed for %s — %s", symbol, e)
    # Yahoo exhausted (401/crumb storm or persistently empty) — try Robinhood.
    try:
        import price_source  # noqa: PLC0415 — host-provided, resolved per repo
        fb = price_source.rh_fallback(symbol, **kwargs)
        if fb is not None and len(fb) >= 5:
            return fb
    except Exception as e:  # noqa: BLE001 — fallback must never break the run
        logger.debug("yf_download: RH fallback failed for %s — %s", symbol, e)
    return None


def fetch_ohlcv(symbol: str, period_days: int = 252) -> dict | None:
    """Fetch ~`period_days` of daily OHLCV; return numpy arrays {close,high,low,volume}.

    Called ONCE per symbol by a fetch-once consensus run, then sliced to each node.
    Uses period= (relative) which survives crumb expiry better than absolute dates.
    Returns ``None`` on failure.
    """
    period_str = "2y" if period_days > 260 else "1y"
    raw = yf_download_with_retry(symbol, period=period_str, interval="1d", auto_adjust=True)
    if raw is None or len(raw) < 20:
        return None
    try:
        close = raw["Close"].squeeze()
        high = raw["High"].squeeze()
        low = raw["Low"].squeeze()
        volume = raw["Volume"].squeeze()
        # Drop NaN ROWS with one shared mask — per-column dropna produced arrays of
        # different lengths whenever a single field was NaN (common on Yahoo partial
        # rows), silently misaligning close[i]/volume[i] pairs downstream.
        mask = close.notna() & high.notna() & low.notna() & volume.notna()
        return {
            "close":  close[mask].values.astype(float),
            "high":   high[mask].values.astype(float),
            "low":    low[mask].values.astype(float),
            "volume": volume[mask].values.astype(float),
        }
    except Exception as e:  # noqa: BLE001
        logger.debug("fetch_ohlcv: parse error for %s: %s", symbol, e)
        return None


# TTL-bounded per-process SPY cache: without it, SPY is re-downloaded once per symbol
# (e.g. 8 identical 3mo fetches in a run). Long-lived processes (server/autopilot)
# import this too, so an unbounded cache would serve stale SPY for days.
_SPY_CACHE: dict[str, tuple[float, np.ndarray]] = {}
_SPY_CACHE_TTL_S = 30 * 60   # 30 min


def _crossed_market_open(cached_at: float, now: float) -> bool:
    """True if the 09:30 ET session open falls between the two timestamps.

    A SPY array cached PRE-open lacks today's bar, while symbol fetches made
    POST-open carry it — the relative-strength node then compares windows
    offset by one session for up to the cache TTL. Invalidate across the
    boundary instead. (Cross-day gaps are already covered by the 30-min TTL.)
    """
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        a = datetime.fromtimestamp(cached_at, et)
        b = datetime.fromtimestamp(now, et)
        session_open = a.replace(hour=9, minute=30, second=0, microsecond=0)
        return a < session_open <= b
    except Exception:  # noqa: BLE001 — guard must never break the fetch
        return False


def fetch_spy_close(days: int = 40) -> np.ndarray | None:
    """SPY close array for the relative-strength benchmark (TTL-cached per process)."""
    cached = _SPY_CACHE.get("close")
    if (
        cached is not None
        and (time.time() - cached[0]) <= _SPY_CACHE_TTL_S
        and not _crossed_market_open(cached[0], time.time())
    ):
        return cached[1]
    raw = yf_download_with_retry("SPY", period="3mo", interval="1d", auto_adjust=True)
    if raw is None or len(raw) < 5:
        return None
    try:
        arr = raw["Close"].squeeze().dropna().values.astype(float)
        _SPY_CACHE["close"] = (time.time(), arr)
        return arr
    except Exception:
        return None


# ── Compatibility aliases — match the engine's existing private import sites,
#    so it can later `from gesh_core.market_fetch import _yf_download_with_retry`
#    (or have consensus re-export these) with zero call-site changes. ──
_yf_download_with_retry = yf_download_with_retry
_fetch_ohlcv = fetch_ohlcv
_fetch_spy_close = fetch_spy_close
