"""``_env_int`` keys not covered by #61 use the same parser.

#61 pinned ``MAX_ORDERS_PER_DAY`` / ``EARNINGS_PROXIMITY_HOURS`` /
``MARKET_REGIME_MA_DAYS``. LIVE quote-age and the consecutive-loss breaker
are the remaining integer knobs: a launchd ``120.0`` / ``3.5`` must fall
back to the conservative default, not silently raise the freshness window
or the loss-streak trip.
"""
from __future__ import annotations

from gesh_core.trading.config import load_risk_config


def test_fractional_looking_price_age_falls_back_to_300(monkeypatch) -> None:
    monkeypatch.setenv("MAX_PRICE_AGE_SECONDS", "120.0")
    assert load_risk_config().max_price_age_seconds == 300


def test_garbage_price_age_falls_back_to_300(monkeypatch) -> None:
    monkeypatch.setenv("MAX_PRICE_AGE_SECONDS", "five-min")
    assert load_risk_config().max_price_age_seconds == 300


def test_fractional_looking_paper_price_age_falls_back(monkeypatch) -> None:
    # 900.0 must not parse as 900 — that would silently tighten the paper
    # freshness window. int("900.0") raises, so the 1800s default stays.
    monkeypatch.setenv("MAX_PRICE_AGE_SECONDS_PAPER", "900.0")
    assert load_risk_config().max_price_age_seconds_paper == 1800


def test_garbage_paper_price_age_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("MAX_PRICE_AGE_SECONDS_PAPER", "abc")
    assert load_risk_config().max_price_age_seconds_paper == 1800


def test_fractional_looking_loss_days_does_not_truncate(monkeypatch) -> None:
    # 4.5 must not become 4 via float-then-int. The conservative default is 3.
    monkeypatch.setenv("MAX_CONSECUTIVE_LOSS_DAYS", "4.5")
    assert load_risk_config().max_consecutive_loss_days == 3


def test_garbage_loss_days_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CONSECUTIVE_LOSS_DAYS", "three")
    assert load_risk_config().max_consecutive_loss_days == 3
