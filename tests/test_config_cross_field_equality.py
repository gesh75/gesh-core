"""R6 leftover: cross-field floors may be equal, and explicit-zero / +int tokens.

#79 only asserted the fail direction (risk-off weaker than base; paper
freshness tighter than live). Equal values are valid. EARNINGS_PROXIMITY_HOURS
documents allow_zero=True. Integer parser accepts a leading plus.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.config import NUMERIC_SPECS, load_risk_config

_NUMERIC_ENV_KEYS = tuple(spec.key for spec in NUMERIC_SPECS)


@pytest.fixture(autouse=True)
def _hermetic_numeric_env(monkeypatch) -> None:
    for key in _NUMERIC_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_risk_off_floor_may_equal_base_confidence(monkeypatch) -> None:
    monkeypatch.setenv("MIN_CONFIDENCE", "0.80")
    monkeypatch.setenv("MIN_CONFIDENCE_RISK_OFF", "0.80")
    cfg = load_risk_config()
    assert cfg.min_confidence == 0.80
    assert cfg.min_confidence_risk_off == 0.80


def test_paper_freshness_may_equal_live_freshness(monkeypatch) -> None:
    monkeypatch.setenv("MAX_PRICE_AGE_SECONDS", "600")
    monkeypatch.setenv("MAX_PRICE_AGE_SECONDS_PAPER", "600")
    cfg = load_risk_config()
    assert cfg.max_price_age_seconds == 600
    assert cfg.max_price_age_seconds_paper == 600


def test_zero_earnings_proximity_hours_is_valid(monkeypatch) -> None:
    monkeypatch.setenv("EARNINGS_PROXIMITY_HOURS", "0")
    assert load_risk_config().earnings_proximity_hours == 0


def test_leading_plus_integer_token_is_valid(monkeypatch) -> None:
    monkeypatch.setenv("MAX_ORDERS_PER_DAY", "+15")
    assert load_risk_config().max_orders_per_day == 15
