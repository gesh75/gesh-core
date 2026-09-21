"""SPY cache invalidation is inclusive on the 09:30 ET open instant.

A pre-open array lacks today's bar. Cached-at 09:25 with a read at exactly
09:30 must refetch; a cache written at 09:30 must serve the rest of the
session. Off-by-one here offsets every relative-strength window by a day.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from gesh_core.market_fetch import _crossed_market_open


def _et_ts(hour: int, minute: int) -> float:
    return datetime(2026, 7, 2, hour, minute, tzinfo=ZoneInfo("America/New_York")).timestamp()


def test_crossed_market_open_now_exactly_open_invalidates() -> None:
    assert _crossed_market_open(_et_ts(9, 25), _et_ts(9, 30)) is True


def test_crossed_market_open_cached_at_open_stays_valid() -> None:
    assert _crossed_market_open(_et_ts(9, 30), _et_ts(9, 35)) is False
