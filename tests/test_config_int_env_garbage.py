"""``_env_int`` only accepts base-10 integer strings.

A launchd/.env typo like ``MAX_ORDERS_PER_DAY=15.0`` looks numeric but
``int('15.0')`` raises, so the parser falls back to the conservative default
of 3 — not 15. Garbage tokens do the same. Pin that so a later 'be liberal'
change cannot silently raise the daily order cap.
"""
from __future__ import annotations

from gesh_core.trading.config import load_risk_config


def test_garbage_max_orders_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.setenv("MAX_ORDERS_PER_DAY", "abc")
    assert load_risk_config().max_orders_per_day == 3


def test_fractional_looking_max_orders_does_not_truncate_to_15(monkeypatch) -> None:
    monkeypatch.setenv("MAX_ORDERS_PER_DAY", "15.0")
    assert load_risk_config().max_orders_per_day == 3


def test_garbage_earnings_proximity_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("EARNINGS_PROXIMITY_HOURS", "two-days")
    assert load_risk_config().earnings_proximity_hours == 48


def test_garbage_regime_ma_days_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_REGIME_MA_DAYS", "200.0")
    assert load_risk_config().market_regime_ma_days == 200
