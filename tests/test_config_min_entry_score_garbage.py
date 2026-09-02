"""Garbage MIN_ENTRY_SCORE must fall back to the 0.35 conviction floor.

Operators set this to disable (0.0) or tighten (0.55). A typo like "high"
must not crash load_risk_config and must not silently disable the floor
(0.0) — it restores the documented default, same as other _env_float knobs.
"""
from __future__ import annotations

from gesh_core.trading.config import load_risk_config


def test_garbage_min_entry_score_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("MIN_ENTRY_SCORE", "high")
    assert load_risk_config().min_entry_score == 0.35


def test_blank_min_entry_score_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("MIN_ENTRY_SCORE", "")
    assert load_risk_config().min_entry_score == 0.35
