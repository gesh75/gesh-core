"""Restart handoff must keep real tickers and drop junk in the same marker.

``restore_candidate_symbols`` already fails closed on wholly-malformed payloads.
A mixed list (valid strings plus ints/empties) is the realistic restart case —
dropping the valid names would wipe today's pre-market universe.
"""
from __future__ import annotations

import json

from gesh_core.trading.autopilot_core import restore_candidate_symbols


def test_restore_keeps_valid_strings_among_junk():
    raw = json.dumps({"date": "2026-07-02", "symbols": ["NVDA", 1, "", None, "HOOD"]})
    assert restore_candidate_symbols(raw, "2026-07-02") == ["NVDA", "HOOD"]
