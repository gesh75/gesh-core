"""Numeric risk-cap env parsing has no finiteness or sign guard.

``_env_float`` / ``_env_int`` accept any parseable value. inf/nan/negative
caps load unchanged (distinct from the CASH_FLOOR fail-closed production
fix). A fractional MAX_ORDERS_PER_DAY is not an int and falls back.
Pin current behavior so a later fail-closed change is reviewable.
"""
from __future__ import annotations

import math

from gesh_core.trading.config import load_risk_config


def test_max_position_pct_inf_and_nan_load_as_parsed(monkeypatch):
    monkeypatch.setenv("MAX_POSITION_PCT", "inf")
    assert math.isinf(load_risk_config().max_position_pct)

    monkeypatch.setenv("MAX_POSITION_PCT", "nan")
    assert math.isnan(load_risk_config().max_position_pct)


def test_negative_cash_buffer_and_daily_loss_load_as_parsed(monkeypatch):
    monkeypatch.setenv("MIN_CASH_BUFFER_USD", "-1000")
    monkeypatch.setenv("MAX_DAILY_LOSS_PCT", "-0.5")
    cfg = load_risk_config()
    assert cfg.min_cash_buffer_usd == -1000.0
    assert cfg.max_daily_loss_pct == -0.5


def test_fractional_max_orders_falls_back(monkeypatch):
    monkeypatch.setenv("MAX_ORDERS_PER_DAY", "3.5")
    assert load_risk_config().max_orders_per_day == 3
