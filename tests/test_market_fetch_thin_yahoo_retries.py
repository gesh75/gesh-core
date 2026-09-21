"""Yahoo frames with 1–4 rows retry, then a trusted fallback may still win.

``yf_download_with_retry`` treats ``len(raw) < 5`` like a miss (not an
exception). Empty-DataFrame exhaustion is on main; this pins the thin
non-empty path so a 3-bar Yahoo response cannot short-circuit retries or
accept a frame that would break ATR / consensus windows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gesh_core import market_fetch as mf


def _df(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Close": np.linspace(100, 130, n),
            "High": np.linspace(101, 131, n),
            "Low": np.linspace(99, 129, n),
            "Volume": np.linspace(1e6, 2e6, n),
        }
    )


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(mf.time, "sleep", lambda *a, **k: None)
    yield


def test_thin_yahoo_retries_then_uses_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def thin(*_a, **_k):
        calls["n"] += 1
        return _df(3)

    monkeypatch.setattr(mf.yf, "download", thin)
    out = mf.yf_download_with_retry("NVDA", period="1y", fallback=lambda symbol, **k: _df(30))
    assert out is not None
    assert len(out) == 30
    assert calls["n"] == mf._YF_MAX_RETRIES


def test_thin_yahoo_and_thin_fallback_return_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mf.yf, "download", lambda *a, **k: _df(4))
    assert mf.yf_download_with_retry("NVDA", fallback=lambda symbol, **k: _df(2)) is None
