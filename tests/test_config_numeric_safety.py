"""R6 — strict numeric safety configuration.

Env/file construction must reject NaN, infinity, negative caps, and malformed
values instead of silently disabling gates. Conservative defaults and valid
overrides stay compatible. Safety-boolean parsing is unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict

import pytest

from gesh_core import allocation_config as ac
from gesh_core import kelly
from gesh_core.trading.config import ConfigError, effective_config, load_risk_config

SAFETY_BOOLS = ("PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE")

NUMERIC_ENV_KEYS = (
    "MAX_POSITION_PCT",
    "MAX_DAILY_LOSS_PCT",
    "MAX_ORDERS_PER_DAY",
    "MIN_CASH_BUFFER_USD",
    "MIN_CONFIDENCE",
    "MIN_ENTRY_SCORE",
    "PAPER_CASH_USD",
    "MAX_PRICE_AGE_SECONDS",
    "MAX_PRICE_AGE_SECONDS_PAPER",
    "MAX_SECTOR_PCT",
    "EARNINGS_PROXIMITY_HOURS",
    "MAX_CONSECUTIVE_LOSS_DAYS",
    "MIN_CONFIDENCE_RISK_OFF",
    "MARKET_REGIME_MA_DAYS",
    "KELLY_MAX_POSITION_PCT",
    "KELLY_MAX_GROSS_PCT",
)

# Material numeric limits that must appear in effective_config settings/hash.
HASHED_NUMERIC_KEYS = (
    "MAX_POSITION_PCT",
    "MAX_DAILY_LOSS_PCT",
    "MAX_ORDERS_PER_DAY",
    "MIN_CASH_BUFFER_USD",
    "MIN_CONFIDENCE",
    "MIN_ENTRY_SCORE",
    "PAPER_CASH_USD",
    "MAX_PRICE_AGE_SECONDS",
    "MAX_PRICE_AGE_SECONDS_PAPER",
    "MAX_SECTOR_PCT",
    "KELLY_MAX_POSITION_PCT",
    "KELLY_MAX_GROSS_PCT",
)


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    for key in (*SAFETY_BOOLS, *NUMERIC_ENV_KEYS):
        monkeypatch.delenv(key, raising=False)


def _assert_refused(key: str, raw: str, fn) -> None:
    with pytest.raises(ConfigError) as exc:
        fn()
    msg = str(exc.value)
    assert key in msg, msg
    # Distinctive raw tokens must not leak. Short numeric fragments like "0"
    # are allowed in range text ("must be > 0").
    token = raw.strip()
    if any(c.isalpha() for c in token):
        assert token not in msg, msg


# ─── invalid env fails construction ───────────────────────────────────────────


@pytest.mark.parametrize(
    "key,raw",
    [
        ("MAX_DAILY_LOSS_PCT", "inf"),
        ("MAX_DAILY_LOSS_PCT", "INF"),
        ("MAX_DAILY_LOSS_PCT", "+inf"),
        ("MAX_DAILY_LOSS_PCT", "-inf"),
        ("MAX_DAILY_LOSS_PCT", "Infinity"),
        ("MAX_DAILY_LOSS_PCT", "nan"),
        ("MAX_DAILY_LOSS_PCT", "NaN"),
        ("MAX_DAILY_LOSS_PCT", "-0.01"),
        ("MAX_DAILY_LOSS_PCT", "0"),
        ("MAX_DAILY_LOSS_PCT", "0.0"),
        ("MAX_DAILY_LOSS_PCT", "not-a-number"),
        ("MAX_DAILY_LOSS_PCT", "1.5"),
        ("MAX_POSITION_PCT", "-0.5"),
        ("MAX_POSITION_PCT", "inf"),
        ("MAX_POSITION_PCT", "nan"),
        ("MAX_POSITION_PCT", "1.1"),
        ("MAX_POSITION_PCT", "abc"),
        ("MIN_CONFIDENCE", "1.5"),
        ("MIN_CONFIDENCE", "-0.1"),
        ("MIN_CONFIDENCE", "nan"),
        ("MIN_CASH_BUFFER_USD", "-100"),
        ("MIN_CASH_BUFFER_USD", "inf"),
        ("PAPER_CASH_USD", "-1"),
        ("PAPER_CASH_USD", "0"),
        ("PAPER_CASH_USD", "nan"),
        ("MAX_SECTOR_PCT", "1.5"),
        ("MAX_SECTOR_PCT", "-0.1"),
        ("MIN_ENTRY_SCORE", "-0.01"),
        ("MIN_ENTRY_SCORE", "1.1"),
        ("MIN_CONFIDENCE_RISK_OFF", "2"),
        ("MAX_ORDERS_PER_DAY", "-1"),
        ("MAX_ORDERS_PER_DAY", "0"),
        ("MAX_ORDERS_PER_DAY", "3.5"),
        ("MAX_ORDERS_PER_DAY", "inf"),
        ("MAX_ORDERS_PER_DAY", "nan"),
        ("MAX_ORDERS_PER_DAY", "many"),
        ("MAX_PRICE_AGE_SECONDS", "0"),
        ("MAX_PRICE_AGE_SECONDS", "-5"),
        ("MAX_PRICE_AGE_SECONDS", "300.5"),
        ("MAX_PRICE_AGE_SECONDS_PAPER", "0"),
        ("MAX_PRICE_AGE_SECONDS_PAPER", "-1"),
        ("EARNINGS_PROXIMITY_HOURS", "-1"),
        ("EARNINGS_PROXIMITY_HOURS", "4.5"),
        ("MAX_CONSECUTIVE_LOSS_DAYS", "0"),
        ("MAX_CONSECUTIVE_LOSS_DAYS", "-2"),
        ("MARKET_REGIME_MA_DAYS", "0"),
        ("MARKET_REGIME_MA_DAYS", "200.2"),
        ("KELLY_MAX_GROSS_PCT", "-0.5"),
        ("KELLY_MAX_GROSS_PCT", "inf"),
        ("KELLY_MAX_GROSS_PCT", "nan"),
        ("KELLY_MAX_GROSS_PCT", "1.1"),
        ("KELLY_MAX_GROSS_PCT", "abc"),
        ("KELLY_MAX_POSITION_PCT", "-0.1"),
        ("KELLY_MAX_POSITION_PCT", "inf"),
        ("KELLY_MAX_POSITION_PCT", "1.5"),
    ],
)
def test_invalid_numeric_env_fails_construction(monkeypatch, key, raw):
    monkeypatch.setenv(key, raw)
    _assert_refused(key, raw, load_risk_config)
    _assert_refused(key, raw, effective_config)


def test_infinite_max_loss_cannot_disable_loss_gate(monkeypatch):
    """MAX_DAILY_LOSS_PCT=inf makes pnl >= -inf always true — refuse to load it."""
    monkeypatch.setenv("MAX_DAILY_LOSS_PCT", "inf")
    with pytest.raises(ConfigError) as exc:
        cfg = load_risk_config()
        # If construction ever started succeeding, inf would disable the gate:
        assert not math.isfinite(cfg.max_daily_loss_pct)
        pytest.fail("infinite max loss was loaded — DAILY_LOSS would never fire")
    assert "MAX_DAILY_LOSS_PCT" in str(exc.value)


def test_negative_kelly_gross_cap_cannot_produce_negative_sizing(monkeypatch):
    monkeypatch.setenv("KELLY_MAX_GROSS_PCT", "-0.25")
    with pytest.raises(ConfigError):
        kelly._max_gross_exposure()
    with pytest.raises(ConfigError):
        load_risk_config()


# ─── zero validity (explicit per setting) ─────────────────────────────────────


def test_zero_min_entry_score_remains_valid(monkeypatch):
    monkeypatch.setenv("MIN_ENTRY_SCORE", "0.0")
    assert load_risk_config().min_entry_score == 0.0


def test_zero_position_cap_is_valid(monkeypatch):
    monkeypatch.setenv("MAX_POSITION_PCT", "0")
    assert load_risk_config().max_position_pct == 0.0


def test_zero_cash_buffer_is_valid(monkeypatch):
    monkeypatch.setenv("MIN_CASH_BUFFER_USD", "0")
    assert load_risk_config().min_cash_buffer_usd == 0.0


def test_zero_kelly_position_cap_is_valid(monkeypatch):
    monkeypatch.setenv("KELLY_MAX_POSITION_PCT", "0")
    assert kelly._max_position_pct() == 0.0
    assert load_risk_config() is not None


# ─── valid conservative settings stay compatible ──────────────────────────────


def test_unset_numeric_env_keeps_conservative_defaults():
    cfg = load_risk_config()
    assert cfg.paper_mode is True
    assert cfg.require_approval is True
    assert cfg.market_regime_gate is True
    assert cfg.max_position_pct == 0.02
    assert cfg.max_daily_loss_pct == 0.01
    assert cfg.max_orders_per_day == 3
    assert cfg.min_cash_buffer_usd == 500.0
    assert cfg.min_confidence == 0.75
    assert cfg.min_entry_score == 0.35
    assert cfg.paper_cash_usd == 100_000.0
    assert cfg.max_price_age_seconds == 300
    assert cfg.max_price_age_seconds_paper == 1800
    assert cfg.max_sector_pct == 0.40


def test_empty_numeric_env_keeps_default(monkeypatch):
    """launchd/.env empty string remains omission, not a malformed number."""
    monkeypatch.setenv("MAX_POSITION_PCT", "")
    monkeypatch.setenv("MAX_ORDERS_PER_DAY", "  ")
    cfg = load_risk_config()
    assert cfg.max_position_pct == 0.02
    assert cfg.max_orders_per_day == 3


@pytest.mark.parametrize(
    "key,raw,attr,expected",
    [
        ("MAX_POSITION_PCT", "0.05", "max_position_pct", 0.05),
        ("MAX_POSITION_PCT", " 0.18 ", "max_position_pct", 0.18),
        ("MAX_DAILY_LOSS_PCT", "0.02", "max_daily_loss_pct", 0.02),
        ("MAX_ORDERS_PER_DAY", "15", "max_orders_per_day", 15),
        ("MIN_CASH_BUFFER_USD", "500", "min_cash_buffer_usd", 500.0),
        ("MIN_CONFIDENCE", "0.8", "min_confidence", 0.8),
        ("MIN_ENTRY_SCORE", "0.55", "min_entry_score", 0.55),
        ("PAPER_CASH_USD", "100000", "paper_cash_usd", 100_000.0),
        ("MAX_PRICE_AGE_SECONDS", "300", "max_price_age_seconds", 300),
        ("KELLY_MAX_GROSS_PCT", "0.30", None, None),
    ],
)
def test_valid_numeric_overrides_accepted(monkeypatch, key, raw, attr, expected):
    monkeypatch.setenv(key, raw)
    cfg = load_risk_config()
    if attr is not None:
        assert getattr(cfg, attr) == expected
    if key == "KELLY_MAX_GROSS_PCT":
        assert kelly._max_gross_exposure() == pytest.approx(0.30)


def test_strict_safety_booleans_still_raise_on_malformed(monkeypatch):
    monkeypatch.setenv("PAPER_MODE", "1")
    with pytest.raises(ConfigError):
        load_risk_config()
    monkeypatch.setenv("PAPER_MODE", "true")
    monkeypatch.setenv("MAX_DAILY_LOSS_PCT", "0.01")
    assert load_risk_config().paper_mode is True


def test_cross_field_risk_off_floor_cannot_be_weaker(monkeypatch):
    monkeypatch.setenv("MIN_CONFIDENCE", "0.90")
    monkeypatch.setenv("MIN_CONFIDENCE_RISK_OFF", "0.50")
    with pytest.raises(ConfigError) as exc:
        load_risk_config()
    assert "MIN_CONFIDENCE_RISK_OFF" in str(exc.value)


def test_cross_field_paper_freshness_cannot_be_tighter_than_live(monkeypatch):
    monkeypatch.setenv("MAX_PRICE_AGE_SECONDS", "1800")
    monkeypatch.setenv("MAX_PRICE_AGE_SECONDS_PAPER", "300")
    with pytest.raises(ConfigError) as exc:
        load_risk_config()
    assert "MAX_PRICE_AGE_SECONDS_PAPER" in str(exc.value)


# ─── effective_config hash + provenance ───────────────────────────────────────


def test_effective_config_includes_numeric_settings():
    eff = effective_config()
    for key in HASHED_NUMERIC_KEYS:
        assert key in eff.settings, key
        setting = eff.settings[key]
        assert setting.name == key
        assert setting.source == "default"
        assert setting.validation_status == "missing"
        assert setting.raw_input == "<missing>"
        assert isinstance(setting.parsed_value, (int, float))
        assert math.isfinite(float(setting.parsed_value))


def test_numeric_limit_change_changes_config_hash(monkeypatch):
    base = effective_config().config_hash
    monkeypatch.setenv("MAX_DAILY_LOSS_PCT", "0.02")
    changed = effective_config().config_hash
    assert base != changed
    monkeypatch.setenv("MAX_DAILY_LOSS_PCT", "0.02")
    again = effective_config().config_hash
    assert changed == again


def test_numeric_hash_is_deterministic_across_calls(monkeypatch):
    monkeypatch.setenv("MAX_POSITION_PCT", "0.05")
    monkeypatch.setenv("MAX_ORDERS_PER_DAY", "15")
    first = effective_config()
    second = effective_config()
    assert first.config_hash == second.config_hash
    assert first == second
    assert hashlib.sha256(first.config_hash.encode()).hexdigest()  # well-formed hex
    assert len(first.config_hash) == 64


def test_config_evidence_contains_no_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-secret-r6-not-for-hash")
    monkeypatch.setenv("GESH_CORE_PAT", "ghp_r6secretpat")
    monkeypatch.setenv("MAX_DAILY_LOSS_PCT", "0.02")
    eff = effective_config()
    blob = eff.config_hash + json.dumps(
        {name: asdict(setting) for name, setting in eff.settings.items()},
        default=str,
    )
    assert "sk-test-secret-r6-not-for-hash" not in blob
    assert "ghp_r6secretpat" not in blob
    assert "0.02" not in eff.settings["MAX_DAILY_LOSS_PCT"].raw_input
    assert eff.settings["MAX_DAILY_LOSS_PCT"].raw_input == "<redacted>"


def test_effective_config_does_not_write_allocation_file(tmp_path, monkeypatch):
    target = tmp_path / "gesh_config.json"
    monkeypatch.setenv("GESH_CONFIG_PATH", str(target))
    effective_config()
    assert not target.exists()


# ─── allocation file caps ─────────────────────────────────────────────────────


def _write_alloc(tmp_path, monkeypatch, **overrides):
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg, allow_nan=True))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))
    return path


@pytest.mark.parametrize(
    "key,value",
    [
        ("max_stock_per_trade", float("inf")),
        ("max_stock_per_trade", float("nan")),
        ("max_stock_per_trade", -1),
        ("max_options_per_trade", float("inf")),
        ("max_options_per_trade", -5),
        ("max_open_positions", -1),
        ("max_open_positions", 0),
        ("max_open_positions", 2.5),
        ("min_cash_buffer", float("inf")),
        ("min_cash_buffer", -10),
        ("stock_allocation_pct", float("nan")),
        ("options_allocation_pct", -1),
    ],
)
def test_invalid_allocation_numeric_fails_construction(tmp_path, monkeypatch, key, value):
    _write_alloc(tmp_path, monkeypatch, **{key: value})
    with pytest.raises(ConfigError) as exc:
        ac.load_config()
    assert key in str(exc.value)


def test_allocation_string_cap_fails_construction(tmp_path, monkeypatch):
    _write_alloc(tmp_path, monkeypatch, max_stock_per_trade="9999")
    with pytest.raises(ConfigError) as exc:
        ac.load_config()
    assert "max_stock_per_trade" in str(exc.value)
    assert "9999" not in str(exc.value)


def test_allocation_cross_field_pct_must_sum_to_100(tmp_path, monkeypatch):
    _write_alloc(tmp_path, monkeypatch, stock_allocation_pct=80.0, options_allocation_pct=80.0)
    with pytest.raises(ConfigError) as exc:
        ac.load_config()
    msg = str(exc.value)
    assert "stock_allocation_pct" in msg or "options_allocation_pct" in msg


def test_valid_allocation_conservative_defaults_load(tmp_path, monkeypatch):
    _write_alloc(tmp_path, monkeypatch)
    cfg = ac.load_config()
    assert cfg["max_stock_per_trade"] == 5000.0
    assert cfg["max_options_per_trade"] == 2000.0
    assert cfg["max_open_positions"] == 5
    assert cfg["min_cash_buffer"] == 500.0
    assert cfg["auto_trade"] is False
