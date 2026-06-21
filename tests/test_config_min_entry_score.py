"""min_entry_score — the P2 entry-conviction floor on consensus raw_score.

Default 0.35 (filters weak BUYs ≥0.25 while keeping solid BUYs + STRONG BUYs ≥0.55).
Env override MIN_ENTRY_SCORE. Entries only; never gates exits.
"""
from __future__ import annotations

import gesh_core.trading.config as config


def test_default_min_entry_score():
    cfg = config.RiskConfig()
    assert cfg.min_entry_score == 0.35


def test_min_entry_score_from_env(monkeypatch):
    monkeypatch.setenv("MIN_ENTRY_SCORE", "0.55")
    cfg = config.load_risk_config()
    assert cfg.min_entry_score == 0.55


def test_min_entry_score_disabled_via_env(monkeypatch):
    monkeypatch.setenv("MIN_ENTRY_SCORE", "0.0")
    cfg = config.load_risk_config()
    assert cfg.min_entry_score == 0.0


def test_min_entry_score_default_when_unset(monkeypatch):
    monkeypatch.delenv("MIN_ENTRY_SCORE", raising=False)
    cfg = config.load_risk_config()
    assert cfg.min_entry_score == 0.35
