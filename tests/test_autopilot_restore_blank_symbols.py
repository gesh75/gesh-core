"""Same-day candidate restore keeps non-empty strings, including whitespace.

``restore_candidate_symbols`` filters with ``isinstance(s, str) and s``.
Empty strings and non-strings are dropped; a whitespace-only token is
truthy and is restored. Pinning that keeps a later strip() from silently
changing which tickers the open-window consensus re-runs.
"""
from __future__ import annotations

import json

from gesh_core.trading.autopilot_core import restore_candidate_symbols

_TODAY = "2026-07-02"


def test_empty_string_dropped_whitespace_kept() -> None:
    raw = json.dumps({"date": _TODAY, "symbols": ["NVDA", "", "  ", "HOOD"]})
    assert restore_candidate_symbols(raw, _TODAY) == ["NVDA", "  ", "HOOD"]


def test_mixed_junk_keeps_only_truthy_strings() -> None:
    raw = json.dumps({"date": _TODAY, "symbols": [1, None, "", "AAPL", False, " "]})
    assert restore_candidate_symbols(raw, _TODAY) == ["AAPL", " "]
