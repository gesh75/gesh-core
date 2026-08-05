"""Stop / take-profit derivation for paper positions.

Extracted from tracker.py (which had grown past the 800-line guideline). Holds the
flat-default ladder + the ATR-adaptive stop logic. tracker.py re-exports these names
for backward compatibility, so `tracker.DEFAULT_STOP_PCT` / `tracker._derive_levels`
etc. keep working.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime

_log = logging.getLogger(__name__)

# ── flat default ladder ───────────────────────────────────────────────────────────
# When an intent carries no explicit stop/target, derive one so the close-scan has
# levels to act on. Without these, positions stay OPEN forever and paper_outcomes
# never grows — the root cause of the 0/30 autonomy-gate stall. Matches
# paper_trading.py's defaults.
DEFAULT_STOP_PCT:   float = 0.05   # 5 % protective stop below (BUY) / above (SELL) entry
DEFAULT_TARGET_PCT: float = 0.12   # 12 % take-profit above (BUY) / below (SELL) entry

# ── ATR-adaptive stops (added 2026-06-09; retuned 2026-06-15) ─────────────────────
# A flat 5 % stop is INSIDE the normal daily noise band for many names, so entries
# get shaken out before any thesis plays out (ORCL stopped in 4 h, AAPL in 4 d). ATR
# scales the stop distance to each symbol's own volatility, clamped to a [MIN, MAX]
# band so it can WIDEN a too-tight stop out of the noise without ever risking more
# than MAX. NOTE: this is the MIRROR IMAGE of the crypto helper — crypto uses ATR as
# a *tightener* (cap downside); here ATR is a *widener with a hard max-loss cap*.
#
# TARGET is an INDEPENDENT ATR multiple (entry ± TARGET_MULT × ATR), NOT an R:R
# multiple of the (clamped) stop. The 2026-06-15 held-out ATR grid validated this
# exact shape — 3.0×ATR stop / 5.0×ATR target / 40d hold — beating the old fixed
# 5/12 exit ~2.8× on a FRESH momentum universe (see docs/SIGNAL_PROFITABILITY_2026-06.md
# + tracker.MAX_HOLD_DAYS). An RR-of-clamped-stop target diverges from the validated
# edge exactly on the volatile momentum names GESH trades (where the stop clamp binds),
# so the target is parameterized off raw ATR to transfer the grid result faithfully.
# MAX cap widened 8 %→15 % to match the grid's clamp so a 3×ATR stop isn't capped
# tighter than what was validated. Any fetch/ATR failure → flat DEFAULT_* fallback.
EQUITY_USE_ATR_STOPS   = os.getenv("EQUITY_USE_ATR_STOPS", "1") not in ("0", "false", "False")
EQUITY_ATR_PERIOD      = int(os.getenv("EQUITY_ATR_PERIOD", "14"))
EQUITY_ATR_STOP_MULT   = float(os.getenv("EQUITY_ATR_STOP_MULT", "3.0"))   # OOS-validated 2026-06-15
EQUITY_MIN_STOP_PCT    = float(os.getenv("EQUITY_MIN_STOP_PCT", "0.03"))   # floor: never tighter than 3 %
EQUITY_MAX_STOP_PCT    = float(os.getenv("EQUITY_MAX_STOP_PCT", "0.15"))   # cap:   never wider   than 15 %
EQUITY_ATR_TARGET_MULT = float(os.getenv("EQUITY_ATR_TARGET_MULT", "5.0")) # target = entry ± TARGET_MULT × ATR


def _atr_levels(
    action: str,
    entry_price: float,
    atr_value: float | None,
) -> tuple[float | None, float | None]:
    """ATR-adaptive (stop, target) — pure, network-free, fully unit-testable.

    Risk distance = clamp(ATR_STOP_MULT × ATR, MIN_STOP_PCT, MAX_STOP_PCT) of entry.
    Reward distance = TARGET_MULT × ATR (independent ATR multiple — NOT R:R of the
    clamped stop; see the module note for why this transfers the OOS grid result).
    BUY → stop below, target above. SELL → inverted.
    Returns (None, None) when inputs are unusable so the caller can fall back to
    the flat DEFAULT_* levels.
    """
    if not entry_price or entry_price <= 0:
        return None, None
    if not atr_value or atr_value <= 0:
        return None, None

    # Tolerate a misconfigured band (MIN > MAX via env) — derive lo/hi from the
    # ordered pair so the clamp can never let risk exceed the intended max.
    lo = entry_price * min(EQUITY_MIN_STOP_PCT, EQUITY_MAX_STOP_PCT)
    hi = entry_price * max(EQUITY_MIN_STOP_PCT, EQUITY_MAX_STOP_PCT)
    risk = max(lo, min(EQUITY_ATR_STOP_MULT * atr_value, hi))
    reward = EQUITY_ATR_TARGET_MULT * atr_value

    if action == "BUY":
        return round(entry_price - risk, 4), round(entry_price + reward, 4)
    # SELL / short — profit when price falls. Floor the target at a positive tick:
    # 5×ATR below entry crosses zero on cheap high-vol names, and a negative target
    # price can never fill (position would ride untouched to MAX_HOLD_DAYS).
    target = max(round(entry_price - reward, 4), round(entry_price * 0.01, 4))
    return round(entry_price + risk, 4), target


# Per-(symbol, UTC-date) ATR cache. Failed fetches are cached too, preventing a bad
# symbol/provider response from repeatedly consuming retries and provider quota.
# The size cap also bounds memory when many distinct symbols are presented.
_ATR_CACHE_MAX_SIZE = 1024
_ATR_CACHE: dict[tuple[str, str], float | None] = {}
_SYMBOL_RE = re.compile(r"[A-Z0-9][A-Z0-9.^=-]{0,31}", re.ASCII | re.IGNORECASE)


def _cache_atr(key: tuple[str, str], value: float | None) -> None:
    if key not in _ATR_CACHE and len(_ATR_CACHE) >= _ATR_CACHE_MAX_SIZE:
        _ATR_CACHE.pop(next(iter(_ATR_CACHE)))
    _ATR_CACHE[key] = value


def _fetch_atr(symbol: str) -> float | None:
    """Fetch ~2 months of daily bars and return the last ATR. Network-bound but
    fully guarded: any failure (no yfinance, 401 crumb, thin data) returns None so
    the caller falls back to a flat stop. Never raises.

    Retry-hardened (3 attempts, 1s/2s backoff) to survive Yahoo's 401-crumb
    throttling — without this the ATR fetch silently fails under the autopilot's
    parallel load and the feature degrades to flat stops invisibly. Logs whether
    ATR fired (with the value) or fell back (with the reason) for observability.
    Cached per symbol per UTC day. NOTE: callers should keep this OFF the DB-write
    path — see record_entry, which calls it with no open SQLite connection held."""
    if (
        not EQUITY_USE_ATR_STOPS
        or not isinstance(symbol, str)
        or _SYMBOL_RE.fullmatch(symbol) is None
    ):
        return None

    key = (symbol, datetime.now(UTC).strftime("%Y-%m-%d"))
    if key in _ATR_CACHE:
        return _ATR_CACHE[key]

    try:
        # Use the shared market_fetch helper: yf.download (period="1y", which Yahoo
        # accepts reliably — the old "2mo" string + yf.Ticker().history fallback
        # intermittently 401'd and silently degraded ATR stops to flat) with the
        # same retry + Robinhood fallback. Returns clean numpy arrays.
        from gesh_core.market_fetch import fetch_ohlcv  # noqa: PLC0415

        from .indicators import atr as _atr_fn

        o = fetch_ohlcv(symbol, period_days=60)
        if not o or len(o.get("close", [])) < EQUITY_ATR_PERIOD + 1:
            _log.info("ATR %s: fell back to flat stop (no/thin bars)", symbol)
            _cache_atr(key, None)
            return None

        a = _atr_fn(o["high"], o["low"], o["close"], EQUITY_ATR_PERIOD)
        if a is None:
            _log.info("ATR %s: fell back to flat stop (ATR computed None)", symbol)
            _cache_atr(key, None)
            return None

        _cache_atr(key, a)
        last_close = float(o["close"][-1])
        _log.info(
            "ATR %s: %.4f (%.2f%% of close) -> adaptive stop",
            symbol, a, (100.0 * a / last_close) if last_close else 0.0,
        )
        return a
    except Exception as e:  # noqa: BLE001 — ATR is best-effort; flat stop is the safe fallback
        _log.info("ATR %s: fell back to flat stop (%s)", symbol, e.__class__.__name__)
        _cache_atr(key, None)
        return None


def _derive_levels(
    action: str,
    entry_price: float,
    stop_loss: float | None,
    take_profit: float | None,
    symbol: str | None = None,
    atr_value: float | None = None,
) -> tuple[float | None, float | None]:
    """
    Fill any missing stop_loss / take_profit from entry_price.

    Order of preference for a MISSING level:
      1. Explicit (non-None) levels on the intent — always preserved.
      2. ATR-adaptive levels (when EQUITY_USE_ATR_STOPS). Uses a precomputed
         `atr_value` when given (preferred — keeps the network OFF the DB-write
         path); otherwise lazily fetches via `_fetch_atr(symbol)`.
      3. Flat DEFAULT_STOP_PCT / DEFAULT_TARGET_PCT fallback.

    BUY → stop below, target above. SELL/short → inverted.
    Levels stay None when entry_price is not a usable positive number.
    """
    if not entry_price or entry_price <= 0:
        return stop_loss, take_profit

    # ATR-adaptive levels only fill the gaps the intent didn't specify.
    if (stop_loss is None or take_profit is None) and EQUITY_USE_ATR_STOPS:
        if atr_value is None and symbol:
            atr_value = _fetch_atr(symbol)
        atr_stop, atr_target = _atr_levels(action, entry_price, atr_value)
        if stop_loss is None and atr_stop is not None:
            stop_loss = atr_stop
        if take_profit is None and atr_target is not None:
            take_profit = atr_target

    if action == "BUY":
        if stop_loss is None:
            stop_loss = round(entry_price * (1 - DEFAULT_STOP_PCT), 4)
        if take_profit is None:
            take_profit = round(entry_price * (1 + DEFAULT_TARGET_PCT), 4)
    else:  # SELL / short — profit when price falls
        if stop_loss is None:
            stop_loss = round(entry_price * (1 + DEFAULT_STOP_PCT), 4)
        if take_profit is None:
            take_profit = round(entry_price * (1 - DEFAULT_TARGET_PCT), 4)
    return stop_loss, take_profit
