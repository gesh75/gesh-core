"""Premarket marker serialization crashes on mixed-type symbol iterables.

``candidates_marker_json`` calls ``sorted(symbols)``. A single non-str in the
08:30 scan raises ``TypeError`` and skips the job-marker write; restart then
restores nothing. Restore already drops non-str list items — the crash is only
on serialize. Pin that so a later coerce/skip cannot silently change the
handoff contract.
"""
from __future__ import annotations

import json

import pytest

from gesh_core.trading.autopilot_core import (
    candidates_marker_json,
    restore_candidate_symbols,
)


def test_string_set_serializes_sorted() -> None:
    raw = candidates_marker_json({"NVDA", "HOOD"}, "2026-07-02")
    assert json.loads(raw) == {"date": "2026-07-02", "symbols": ["HOOD", "NVDA"]}


@pytest.mark.parametrize("symbols", [["NVDA", 123], ["NVDA", None], {("NVDA",), "HOOD"}])
def test_mixed_types_raise_typeerror_on_serialize(symbols) -> None:
    with pytest.raises(TypeError):
        candidates_marker_json(symbols, "2026-07-02")


def test_restore_after_failed_serialize_is_empty() -> None:
    # Characterize the restart path: no marker persisted → empty candidate set.
    assert restore_candidate_symbols(None, "2026-07-02") == []
