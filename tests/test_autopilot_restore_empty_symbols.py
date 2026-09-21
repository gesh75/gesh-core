"""Same-day empty candidate lists must restore as empty, not as malformed.

A pre-market scan that finds nothing still writes ``{"date": today, "symbols": []}``.
On restart that payload is valid — it must not be treated as corrupt (which a
later 'recovery' might replace with yesterday's universe) and must not invent
tickers. Distinct from mixed-junk restore (keeps valid names) and non-list
``symbols`` (fails closed).
"""
from __future__ import annotations

import json

from gesh_core.trading.autopilot_core import (
    candidates_marker_json,
    restore_candidate_symbols,
)


def test_same_day_empty_list_restores_empty() -> None:
    raw = json.dumps({"date": "2026-07-02", "symbols": []})
    assert restore_candidate_symbols(raw, "2026-07-02") == []


def test_marker_roundtrip_of_empty_iterable_is_empty() -> None:
    raw = candidates_marker_json([], "2026-07-02")
    assert json.loads(raw) == {"date": "2026-07-02", "symbols": []}
    assert restore_candidate_symbols(raw, "2026-07-02") == []
