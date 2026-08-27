"""_fetch_profile fail-closed contract (network-free).

compute_fair_value is already characterized with a patched profile. The live
helper must still refuse a bad/missing Yahoo beta rather than abort the DCF
or silently treat 0 / 6 as a usable coefficient.
"""
from __future__ import annotations

import yfinance as yf

from gesh_core.dcf.fair_value import DEFAULT_BETA, _fetch_profile


class _Ticker:
    def __init__(self, info):
        self.info = info


def test_fetched_beta_within_usable_range(monkeypatch):
    monkeypatch.setattr(yf, "Ticker", lambda _s: _Ticker({"beta": 1.4, "sector": "Technology"}))
    beta, fetched, sector = _fetch_profile("AMD")
    assert fetched is True
    assert beta == 1.4
    assert sector == "Technology"


def test_missing_or_out_of_range_beta_uses_default(monkeypatch):
    monkeypatch.setattr(yf, "Ticker", lambda _s: _Ticker({"beta": 0, "sector": "Technology"}))
    beta, fetched, sector = _fetch_profile("AMD")
    assert (beta, fetched, sector) == (DEFAULT_BETA, False, "Technology")

    monkeypatch.setattr(yf, "Ticker", lambda _s: _Ticker({"beta": 6.0, "sector": "Healthcare"}))
    beta, fetched, sector = _fetch_profile("LLY")
    assert (beta, fetched, sector) == (DEFAULT_BETA, False, "Healthcare")

    monkeypatch.setattr(yf, "Ticker", lambda _s: _Ticker({}))
    beta, fetched, sector = _fetch_profile("ZZZ")
    assert (beta, fetched) == (DEFAULT_BETA, False)
    assert sector is None


def test_profile_exception_does_not_abort(monkeypatch):
    def boom(_symbol):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(yf, "Ticker", boom)
    assert _fetch_profile("AMD") == (DEFAULT_BETA, False, None)
