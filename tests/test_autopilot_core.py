"""Shared autopilot building blocks (PR8 phase 1)."""
from __future__ import annotations

import json

import pytest

from gesh_core.trading.autopilot_core import (
    CANDIDATE_MARKER,
    candidates_marker_json,
    entry_floor_blocks,
    restore_candidate_symbols,
    stop_sweep_intent,
)

# ── entry_floor_blocks ────────────────────────────────────────────────────────

@pytest.mark.parametrize("action,raw,floor,blocked", [
    ("BUY", 0.26, 0.35, True),    # weak BUY below the floor → dropped
    ("BUY", 0.35, 0.35, False),   # at the floor → kept
    ("BUY", 0.60, 0.35, False),   # strong → kept
    ("SELL", -0.90, 0.35, False), # managed exit — NEVER gated
    ("HOLD", 0.00, 0.35, False),  # never reaches execution anyway
])
def test_entry_floor(action, raw, floor, blocked):
    assert entry_floor_blocks(action, raw, floor) is blocked


# ── candidate marker round-trip ───────────────────────────────────────────────

def test_marker_roundtrip_same_day():
    raw = candidates_marker_json({"NVDA", "HOOD"}, "2026-07-02")
    assert restore_candidate_symbols(raw, "2026-07-02") == ["HOOD", "NVDA"]


def test_stale_marker_restores_nothing():
    raw = candidates_marker_json(["OLD"], "2020-01-01")
    assert restore_candidate_symbols(raw, "2026-07-02") == []


@pytest.mark.parametrize("raw", [None, "", "not json", "[]", '{"symbols": "x"}',
                                 json.dumps({"date": "2026-07-02", "symbols": [1, None]})])
def test_malformed_marker_restores_nothing(raw):
    assert restore_candidate_symbols(raw, "2026-07-02") == []


def test_restore_candidate_symbols_filters_non_strings_keeps_valid():
    raw = json.dumps({"date": "2026-07-02", "symbols": [1, "NVDA", "", None, "hood"]})
    assert restore_candidate_symbols(raw, "2026-07-02") == ["NVDA", "hood"]


def test_marker_key_is_stable():
    assert CANDIDATE_MARKER == "premarket_candidates"  # persisted in job_markers


# ── stop_sweep_intent ─────────────────────────────────────────────────────────

def test_stop_sweep_intent_is_gate_valid_full_close():
    intent = stop_sweep_intent("HOOD", price=90.0, stop=95.0, book="paper")
    assert intent.validate() == []             # the product bug this prevents
    assert intent.action == "SELL"
    assert intent.target_position_pct == 0.0   # full close
    assert intent.source == "stop_sweep"
    assert "paper" in (intent.rationale or "")
    assert "90.00" in intent.rationale and "95.00" in intent.rationale
