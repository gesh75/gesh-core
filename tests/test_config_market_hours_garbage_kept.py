"""MARKET_* hour/timezone strings are not parsed — garbage is kept as-is.

Unlike the safety booleans (fail-closed) and numeric caps (_env_float
fallback), these three env vars are raw strings. A typo becomes the
effective session window / zone name. Pin that so a later validator is
reviewable and so empty-string handling stays distinct (claimed elsewhere).
"""
from __future__ import annotations

from gesh_core.trading.config import load_risk_config


def test_garbage_market_hours_and_timezone_are_kept(monkeypatch):
    monkeypatch.setenv("MARKET_OPEN_HHMM", "25:99")
    monkeypatch.setenv("MARKET_CLOSE_HHMM", "not-a-time")
    monkeypatch.setenv("MARKET_TIMEZONE", "Not/AZone")
    cfg = load_risk_config()
    assert cfg.market_open_hhmm == "25:99"
    assert cfg.market_close_hhmm == "not-a-time"
    assert cfg.market_timezone == "Not/AZone"


def test_market_hours_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("MARKET_OPEN_HHMM", raising=False)
    monkeypatch.delenv("MARKET_CLOSE_HHMM", raising=False)
    monkeypatch.delenv("MARKET_TIMEZONE", raising=False)
    cfg = load_risk_config()
    assert cfg.market_open_hhmm == "09:30"
    assert cfg.market_close_hhmm == "16:00"
    assert cfg.market_timezone == "America/New_York"
