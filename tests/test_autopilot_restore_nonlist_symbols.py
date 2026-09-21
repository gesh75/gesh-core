"""Same-day restart markers must fail closed when `symbols` is not a list.

``restore_candidate_symbols`` already drops stale/malformed payloads. The
leftover case is a matching date with a string or object in `symbols` —
iterating that would TypeError and wipe the open-window handoff.
"""

from __future__ import annotations

import json

import pytest

from gesh_core.trading.autopilot_core import restore_candidate_symbols


@pytest.mark.parametrize(
    "symbols",
    [
        "NVDA",
        {"NVDA": True},
        3,
        None,
    ],
)
def test_restore_same_day_nonlist_symbols_is_empty(symbols: object) -> None:
    raw = json.dumps({"date": "2026-07-02", "symbols": symbols})
    assert restore_candidate_symbols(raw, "2026-07-02") == []
