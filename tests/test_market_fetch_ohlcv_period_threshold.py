"""fetch_ohlcv period string flips at 260 days (1y vs 2y).

The Yahoo period is what the retry helper actually requests. A regression
that always sends 1y would silently truncate a 2y lookback used by longer
consensus windows; always sending 2y inflates payload and crumb pressure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gesh_core import market_fetch as mf


def _df(n: int = 80) -> pd.DataFrame:
    return pd.DataFrame({
        "Close": np.linspace(100, 130, n),
        "High": np.linspace(101, 131, n),
        "Low": np.linspace(99, 129, n),
        "Volume": np.linspace(1e6, 2e6, n),
    })


def test_period_days_threshold_selects_1y_then_2y(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str | None] = []

    def record(*_a: object, **k: object) -> pd.DataFrame:
        period = k.get("period")
        seen.append(period if isinstance(period, str) else None)
        return _df()

    monkeypatch.setattr(mf, "yf_download_with_retry", record)
    assert mf.fetch_ohlcv("NVDA", period_days=100) is not None
    assert mf.fetch_ohlcv("NVDA", period_days=260) is not None
    assert mf.fetch_ohlcv("NVDA", period_days=261) is not None
    assert seen == ["1y", "1y", "2y"]
