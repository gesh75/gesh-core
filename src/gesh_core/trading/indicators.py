"""Lightweight equity technical indicators.

Equities had no standalone ATR helper — the only true-range math lived buried
inside regime.py's ADX calc. This module exposes a clean, tested ATR (Wilder
smoothing) for the ATR-adaptive stop logic in tracker.py. Math ported from the
crypto side (crypto_indicators.atr) which is the proven reference.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def atr(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    period: int = 14,
) -> float | None:
    """Average True Range (Wilder smoothing). Returns the LAST ATR value.

    Returns None when there is not enough data, or the result is non-finite —
    callers fall back to a fixed-% stop on None (never crash on bad data).
    """
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    if len(c) < period + 1 or len(h) != len(c) or len(l) != len(c):
        return None

    tr = np.maximum(
        h[1:] - l[1:],
        np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])),
    )
    if len(tr) < period:
        return None

    # Wilder smoothing: seed with the SMA of the first `period` TRs, then EMA.
    a = float(np.mean(tr[:period]))
    for i in range(period, len(tr)):
        a = (a * (period - 1) + float(tr[i])) / period

    if not np.isfinite(a) or a <= 0:
        return None
    return a
