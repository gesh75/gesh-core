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


@pytest.mark.parametrize("val,expected", [
    ("1", True), ("true", True), ("YES", True), ("on", True),
    ("0", False), ("false", False), ("no", False), ("", False),
])
def test_paper_mode_env_parsing(monkeypatch, val, expected):
    monkeypatch.setenv("PAPER_MODE", val)
    assert load_risk_config().paper_mode is expected
