"""Parity tests for gesh_core.trading.config (Phase 3.4).

Pins the ULTRA-CONSERVATIVE defaults (paper-mode safety boundary — rules
#32/#36/#40) and the superset field set + robust env parsing. A regression here
could flip live trading on, so these defaults are asserted explicitly.
"""

from __future__ import annotations

import dataclasses

import pytest

from gesh_core.trading import config
from gesh_core.trading.config import RiskConfig, load_risk_config


@pytest.fixture(autouse=True)
def clear_safety_env(monkeypatch):
    """Remove safety variables for each test and restore inherited values afterward."""
    for key in ("PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"):
        monkeypatch.delenv(key, raising=False)


def test_module_loads_from_gesh_core():
    assert "gesh_core" in (config.__file__ or "")


# ─── safety defaults (must never silently change) ─────────────────────────────


def test_paper_mode_defaults_safe():
    cfg = RiskConfig()
    assert cfg.paper_mode is True
    assert cfg.require_approval is True
    assert cfg.max_position_pct == 0.02
    assert cfg.max_daily_loss_pct == 0.01
    assert cfg.min_confidence == 0.75
    assert cfg.paper_cash_usd == 100_000.0


def test_load_defaults_paper_when_env_unset(monkeypatch):
    for k in ("PAPER_MODE", "REQUIRE_APPROVAL", "MAX_POSITION_PCT"):
        monkeypatch.delenv(k, raising=False)
    cfg = load_risk_config()
    assert cfg.paper_mode is True and cfg.require_approval is True


def test_frozen_dataclass():
    cfg = RiskConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.paper_mode = False  # frozen → cannot mutate


# ─── superset fields (product gains these) ────────────────────────────────────


def test_superset_safety_gate_fields_present():
    cfg = RiskConfig()
    assert cfg.max_sector_pct == 0.40
    assert cfg.earnings_proximity_hours == 48
    assert cfg.max_consecutive_loss_days == 3
    assert cfg.min_confidence_risk_off == 0.85
    assert cfg.market_regime_gate is True
    assert cfg.market_regime_ma_days == 200


# ─── env overrides + robust parsing ───────────────────────────────────────────


def test_env_override_applies(monkeypatch):
    monkeypatch.setenv("MAX_POSITION_PCT", "0.05")
    monkeypatch.setenv("MAX_ORDERS_PER_DAY", "15")
    cfg = load_risk_config()
    assert cfg.max_position_pct == 0.05
    assert cfg.max_orders_per_day == 15


def test_empty_string_env_falls_back_to_default(monkeypatch):
    # launchd/.env can set an empty value — must not crash, must use default.
    monkeypatch.setenv("MAX_POSITION_PCT", "")
    monkeypatch.setenv("MAX_ORDERS_PER_DAY", "")
    cfg = load_risk_config()
    assert cfg.max_position_pct == 0.02
    assert cfg.max_orders_per_day == 3


def test_garbage_env_falls_back(monkeypatch):
    monkeypatch.setenv("MAX_DAILY_LOSS_PCT", "not-a-number")
    assert load_risk_config().max_daily_loss_pct == 0.01


@pytest.mark.parametrize("token", ("nan", "NaN", "inf", "+inf", "-inf", "Infinity"))
def test_nonfinite_env_falls_back_to_defaults(monkeypatch, token):
    """launchd/.env can persist nan/inf; those must not disable safety caps.

    `0.4 < nan` and `0.03 > inf` are both False, so a parsed NaN/Inf
    min_confidence / max_position_pct / max_daily_loss_pct would let a LIVE
    order through the corresponding gate.
    """
    monkeypatch.setenv("MIN_CONFIDENCE", token)
    monkeypatch.setenv("MAX_POSITION_PCT", token)
    monkeypatch.setenv("MAX_DAILY_LOSS_PCT", token)
    monkeypatch.setenv("MIN_CASH_BUFFER_USD", token)
    monkeypatch.setenv("MIN_ENTRY_SCORE", token)
    monkeypatch.setenv("PAPER_CASH_USD", token)
    cfg = load_risk_config()
    assert cfg.min_confidence == 0.75
    assert cfg.max_position_pct == 0.02
    assert cfg.max_daily_loss_pct == 0.01
    assert cfg.min_cash_buffer_usd == 500.0
    assert cfg.min_entry_score == 0.35
    assert cfg.paper_cash_usd == 100_000.0


def test_nonfinite_min_confidence_would_fail_open_without_the_guard(monkeypatch):
    """Characterization: IEEE comparisons against NaN never trip a 'too low' gate."""
    assert not (0.10 < float("nan"))
    monkeypatch.setenv("MIN_CONFIDENCE", "nan")
    cfg = load_risk_config()
    assert 0.10 < cfg.min_confidence


def test_paper_mode_env_parsing(monkeypatch):
    """Compatibility test for the strict PAPER_MODE contract (updated per P0-B).

    Missing retains default; only trimmed case-insensitive true/false accepted;
    blank, all legacy aliases (1/0/yes/no/y/n/on/off), and malformed raise ConfigError.
    Concise — extensive matrix lives in test_config_strict_safety.py.
    """
    # Missing retains documented default
    monkeypatch.delenv("PAPER_MODE", raising=False)
    assert load_risk_config().paper_mode is True

    # Valid true/false (case-insensitive after trim) only
    for val in ("true", "True", " TRUE ", " true\t", "\nfalse "):
        monkeypatch.setenv("PAPER_MODE", val)
        assert load_risk_config().paper_mode is (val.strip().lower() == "true")

    # Legacy aliases now raise (P0-B contract)
    for bad in ("1", "0", "yes", "no", "y", "n", "on", "off"):
        monkeypatch.setenv("PAPER_MODE", bad)
        with pytest.raises(config.ConfigError):
            load_risk_config()

    # Blank raises ConfigError (never silent False)
    monkeypatch.setenv("PAPER_MODE", "")
    with pytest.raises(config.ConfigError):
        load_risk_config()

    # Malformed raises ConfigError (never silent False)
    monkeypatch.setenv("PAPER_MODE", "maybe")
    with pytest.raises(config.ConfigError):
        load_risk_config()
