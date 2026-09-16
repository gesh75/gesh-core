"""R6 leftover: inclusive extrema and leftover int tokens.

#79 / test_config_numeric_safety pin the refuse list. These are the
adjacent accept/reject edges: max=1.0, zero-allowed floors, a leading
plus on a float, and scientific-notation integers (``1e2`` is not a
digit token).
"""

from __future__ import annotations

import pytest

from gesh_core.trading.config import NUMERIC_SPECS, ConfigError, load_risk_config

_NUMERIC_KEYS = tuple(spec.key for spec in NUMERIC_SPECS)
_SAFETY_BOOLS = ("PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE")


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    for key in (*_SAFETY_BOOLS, *_NUMERIC_KEYS):
        monkeypatch.delenv(key, raising=False)


def test_max_daily_loss_at_one_is_valid(monkeypatch) -> None:
    monkeypatch.setenv("MAX_DAILY_LOSS_PCT", "1.0")
    assert load_risk_config().max_daily_loss_pct == 1.0


def test_zero_allowed_floors_stay_valid(monkeypatch) -> None:
    monkeypatch.setenv("MIN_CONFIDENCE", "0")
    monkeypatch.setenv("MAX_SECTOR_PCT", "0")
    cfg = load_risk_config()
    assert cfg.min_confidence == 0.0
    assert cfg.max_sector_pct == 0.0


def test_leading_plus_float_is_accepted(monkeypatch) -> None:
    monkeypatch.setenv("MAX_POSITION_PCT", "+0.05")
    assert load_risk_config().max_position_pct == pytest.approx(0.05)


def test_scientific_int_is_rejected_without_echo(monkeypatch) -> None:
    monkeypatch.setenv("MAX_ORDERS_PER_DAY", "1e2")
    with pytest.raises(ConfigError) as exc:
        load_risk_config()
    msg = str(exc.value)
    assert "MAX_ORDERS_PER_DAY" in msg
    assert "1e2" not in msg
