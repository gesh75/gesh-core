"""``_fetch_profile`` only accepts a strictly-positive beta below 5.

``if beta and 0 < float(beta) < 5`` treats 0 (valid, uncorrelated) and 5.0
(the exclusive upper bound) as missing — both return ``DEFAULT_BETA`` with
``was_fetched=False`` so the headline is not Blume-adjusted off junk. A
later inclusive bound would silently re-rate every name Yahoo marks 0 or 5.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import yfinance as yf

from gesh_core.dcf.fair_value import DEFAULT_BETA, _fetch_profile


def _patch_info(monkeypatch: pytest.MonkeyPatch, info: dict) -> None:
    monkeypatch.setattr(yf, "Ticker", lambda _symbol: SimpleNamespace(info=info))


def test_zero_beta_is_treated_as_unfetched(monkeypatch: pytest.MonkeyPatch):
    _patch_info(monkeypatch, {"beta": 0, "sector": "Technology"})
    raw, fetched, sector = _fetch_profile("AMD")
    assert raw == DEFAULT_BETA
    assert fetched is False
    assert sector == "Technology"


def test_beta_five_is_exclusive_and_unfetched(monkeypatch: pytest.MonkeyPatch):
    _patch_info(monkeypatch, {"beta": 5.0, "sector": "Technology"})
    raw, fetched, sector = _fetch_profile("AMD")
    assert raw == DEFAULT_BETA
    assert fetched is False
    assert sector == "Technology"


def test_beta_just_inside_the_band_is_fetched(monkeypatch: pytest.MonkeyPatch):
    _patch_info(monkeypatch, {"beta": 4.99, "sector": "Technology"})
    raw, fetched, sector = _fetch_profile("AMD")
    assert raw == pytest.approx(4.99)
    assert fetched is True
    assert sector == "Technology"


def test_negative_beta_is_unfetched(monkeypatch: pytest.MonkeyPatch):
    _patch_info(monkeypatch, {"beta": -0.4, "sector": "Technology"})
    raw, fetched, _sector = _fetch_profile("AMD")
    assert raw == DEFAULT_BETA
    assert fetched is False


def test_missing_info_and_ticker_errors_fail_open(monkeypatch: pytest.MonkeyPatch):
    _patch_info(monkeypatch, {})
    raw, fetched, sector = _fetch_profile("AMD")
    assert (raw, fetched, sector) == (DEFAULT_BETA, False, None)

    def _boom(_symbol):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(yf, "Ticker", _boom)
    raw, fetched, sector = _fetch_profile("AMD")
    assert (raw, fetched, sector) == (DEFAULT_BETA, False, None)
