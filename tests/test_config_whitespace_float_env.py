"""Float env parsing accepts padded numbers and rejects whitespace-only.

``float('  0.05  ')`` succeeds, so a launchd value with surrounding spaces
must apply. A whitespace-only value is not ``''`` (the empty-string
fast-path) — it hits ``ValueError`` and must still fall back to the
ultra-conservative default rather than crash the process.
"""
from __future__ import annotations

from gesh_core.trading.config import load_risk_config


def test_padded_max_position_pct_parses(monkeypatch) -> None:
    monkeypatch.setenv("MAX_POSITION_PCT", "  0.05  ")
    assert load_risk_config().max_position_pct == 0.05


def test_whitespace_only_max_position_pct_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("MAX_POSITION_PCT", "   ")
    assert load_risk_config().max_position_pct == 0.02


def test_padded_min_confidence_parses(monkeypatch) -> None:
    monkeypatch.setenv("MIN_CONFIDENCE", "\t0.80\n")
    assert load_risk_config().min_confidence == 0.80
