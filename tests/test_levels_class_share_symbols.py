"""ATR fetch must accept class-share / exchange-suffix tickers.

``_SYMBOL_RE`` allows ``.`` ``-`` ``^`` ``=`` so BRK.B / RDS-A / BF.B reach
``fetch_ohlcv``. #47 already rejects spaces and 33-char junk without a
network call. If the allowlist is tightened to ``[A-Z]+`` those names
silently degrade to the flat 5/12 ladder.
"""
from __future__ import annotations

import numpy as np

import gesh_core.market_fetch as market_fetch
from gesh_core.trading import levels


def _arrays(n=40):
    base = np.linspace(100, 120, n)
    return {"high": base + 2, "low": base - 2, "close": base, "volume": np.full(n, 1_000.0)}


def test_class_share_and_suffix_tickers_are_fetched(monkeypatch):
    levels._ATR_CACHE.clear()
    seen: list[str] = []

    def fake(symbol, period_days=252):
        seen.append(symbol)
        return _arrays()

    monkeypatch.setattr(market_fetch, "fetch_ohlcv", fake)
    for symbol in ("BRK.B", "RDS-A", "BF.B", "SPY"):
        value = levels._fetch_atr(symbol)
        assert value is not None and value > 0
    assert seen == ["BRK.B", "RDS-A", "BF.B", "SPY"]


def test_equals_fx_ticker_is_fetched_but_leading_caret_is_rejected(monkeypatch):
    # The allowlist permits ``^`` after the first character (BRK^B) but the
    # first char must be alphanumeric — Yahoo index tickers like ``^GSPC``
    # currently skip ATR and silently use the flat ladder.
    levels._ATR_CACHE.clear()
    seen: list[str] = []
    monkeypatch.setattr(
        market_fetch,
        "fetch_ohlcv",
        lambda s, **k: (seen.append(s), _arrays())[1],
    )
    assert levels._fetch_atr("EURUSD=X") is not None
    assert levels._fetch_atr("^GSPC") is None
    assert seen == ["EURUSD=X"]
