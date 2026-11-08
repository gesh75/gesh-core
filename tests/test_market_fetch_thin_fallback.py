"""A thin host fallback must not become a consensus OHLCV series.

Yahoo already requires ≥5 rows. The leftover is a trusted fallback that
returns 4 bars — that must fail closed as None, same as an empty Yahoo
download, or relative-strength / ATR will size off a stub window.
"""

from __future__ import annotations

import pandas as pd
import pytest

from gesh_core import market_fetch as mf


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mf.time, "sleep", lambda *a, **k: None)


def test_yf_download_thin_fallback_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mf.yf, "download", lambda *a, **k: pd.DataFrame())
    thin = pd.DataFrame({"Close": [100.0, 101.0, 102.0, 103.0]})
    assert mf.yf_download_with_retry("NVDA", period="2y", fallback=lambda *_a, **_k: thin) is None
