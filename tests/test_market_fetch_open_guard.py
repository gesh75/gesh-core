"""_crossed_market_open must fail open (return False) on unusable timestamps.

The SPY cache invalidation guard is best-effort: a TypeError/OSError inside
the ET conversion must not break fetch_spy_close. Returning True on garbage
would force a refetch storm; returning False keeps the TTL cache.
"""
from __future__ import annotations

from gesh_core import market_fetch as mf


def test_crossed_market_open_fail_open_on_bad_input():
    assert mf._crossed_market_open("not-a-timestamp", 1.0) is False
    assert mf._crossed_market_open(float("nan"), 1.0) is False
