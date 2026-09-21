"""Host-supplied Yahoo fallback must never break the fetch.

``yf_download_with_retry`` already returns None when Yahoo is empty. A
trusted host callback that *raises* (RH outage, bad kwargs) is a separate
path — it is caught and the caller still gets None, never an exception
into consensus / ATR.
"""
from __future__ import annotations

import pandas as pd
import pytest

from gesh_core import market_fetch as mf


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(mf.time, "sleep", lambda *a, **k: None)


def test_fallback_exception_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(mf.yf, "download", lambda *a, **k: pd.DataFrame())
    calls = {"n": 0}

    def boom(symbol, **kwargs):
        calls["n"] += 1
        raise RuntimeError("robinhood unavailable")

    assert mf.yf_download_with_retry("NVDA", period="2y", fallback=boom) is None
    assert calls["n"] == 1



def test_fallback_none_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(mf.yf, "download", lambda *a, **k: pd.DataFrame())
    assert mf.yf_download_with_retry("NVDA", period="2y", fallback=lambda *a, **k: None) is None
