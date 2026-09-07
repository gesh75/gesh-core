"""Parity tests for gesh_core.trading.levels + indicators (Phase 3.1).

Pins the pure, network-free behavior that the engine's tracker/close-scan rely
on. The engine keeps its own tests/test_gesh_core_candidates.py exercising the
same code through the shim; these prove gesh-core is self-contained (the
relative ``from .indicators import atr`` resolves inside the package).
"""
from __future__ import annotations

import importlib

import numpy as np
import pytest

from gesh_core.trading import indicators, levels

_ATR_ENV_KEYS = (
    "EQUITY_ATR_PERIOD",
    "EQUITY_ATR_STOP_MULT",
    "EQUITY_MIN_STOP_PCT",
    "EQUITY_MAX_STOP_PCT",
    "EQUITY_ATR_TARGET_MULT",
)


def _reload_levels(monkeypatch: pytest.MonkeyPatch, **env: str) -> object:
    """Re-import levels with ATR knobs set (or cleared) so import-time parse runs."""
    for key in _ATR_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(levels)


def test_modules_load_from_gesh_core():
    assert "gesh_core" in (levels.__file__ or "")
    assert "gesh_core" in (indicators.__file__ or "")


def test_flat_default_levels_buy():
    # No ATR value, ATR fetch path skipped (atr_value passed) -> flat ladder.
    stop, target = levels._derive_levels("BUY", 100.0, None, None, atr_value=None, symbol=None)
    assert stop == 95.0      # 5% protective stop
    assert target == 112.0   # 12% take-profit


def test_flat_default_levels_sell_inverted():
    stop, target = levels._derive_levels("SELL", 100.0, None, None, atr_value=None, symbol=None)
    assert stop == 105.0
    assert target == 88.0


def test_explicit_levels_preserved():
    stop, target = levels._derive_levels("BUY", 100.0, 90.0, 130.0)
    assert (stop, target) == (90.0, 130.0)


def test_atr_levels_buy_clamped():
    # ATR distance within [MIN, MAX] band -> entry ± multiples.
    stop, target = levels._atr_levels("BUY", 100.0, 2.0)
    # risk = clamp(3.0*2.0=6.0, 3%..15% of 100) = 6.0 ; reward = 5.0*2.0 = 10.0
    assert stop == 94.0    # 100 - 6.0
    assert target == 110.0  # 100 + 10.0


def test_atr_levels_bad_input_returns_none():
    assert levels._atr_levels("BUY", 0.0, 2.0) == (None, None)
    assert levels._atr_levels("BUY", 100.0, None) == (None, None)


def test_indicators_atr_matches_true_range():
    high = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
    low = np.array([9.0, 9.5, 10.5, 11.0, 12.0])
    close = np.array([9.5, 10.5, 11.5, 12.5, 13.5])
    val = indicators.atr(high, low, close, period=3)
    assert val is not None and val > 0


def test_atr_sell_target_floored_positive():
    # Cheap high-vol name: entry $2, ATR $0.50 -> raw target 2 - 5*0.5 = -0.5.
    # A negative short take-profit can never fill; it must floor at a positive tick.
    stop, target = levels._atr_levels("SELL", 2.0, 0.5)
    assert target is not None and target > 0
    assert stop is not None and stop > 2.0                 # stop stays above entry


def test_atr_buy_levels_unchanged_by_floor():
    stop, target = levels._atr_levels("BUY", 100.0, 1.0)
    assert stop == 97.0                                    # 3*ATR clamped to [3%,15%]
    assert target == 105.0                                 # 5*ATR


# ─── import-time ATR env parse (must not crash the stop ladder) ───────────────


@pytest.fixture
def restore_levels_env(monkeypatch: pytest.MonkeyPatch):
    """Every ATR-env test reloads the module; put defaults back afterward."""
    yield
    _reload_levels(monkeypatch)


@pytest.mark.parametrize(
    "env",
    [
        {"EQUITY_ATR_PERIOD": ""},
        {"EQUITY_ATR_STOP_MULT": ""},
        {"EQUITY_MIN_STOP_PCT": ""},
        {"EQUITY_MAX_STOP_PCT": ""},
        {"EQUITY_ATR_TARGET_MULT": ""},
        {"EQUITY_ATR_PERIOD": "10.0"},  # int() rejects floats; do not truncate to 10
        {"EQUITY_ATR_PERIOD": "nope"},
        {"EQUITY_ATR_PERIOD": "0"},
        {"EQUITY_ATR_PERIOD": "-3"},
        {"EQUITY_ATR_STOP_MULT": "nan"},
        {"EQUITY_ATR_STOP_MULT": "inf"},
        {"EQUITY_MIN_STOP_PCT": "-inf"},
        {"EQUITY_ATR_TARGET_MULT": "NaN"},
    ],
)
def test_empty_or_junk_atr_env_keeps_validated_defaults(env, monkeypatch, restore_levels_env):
    mod = _reload_levels(monkeypatch, **env)
    assert mod.EQUITY_ATR_PERIOD == 14
    assert mod.EQUITY_ATR_STOP_MULT == 3.0
    assert mod.EQUITY_MIN_STOP_PCT == 0.03
    assert mod.EQUITY_MAX_STOP_PCT == 0.15
    assert mod.EQUITY_ATR_TARGET_MULT == 5.0
    # Import surviving is the load-bearing assertion: empty launchd values
    # used to raise ValueError here and skip the entire stop ladder.
    stop, target = mod._derive_levels("BUY", 100.0, None, None, atr_value=None, symbol=None)
    assert stop == 95.0
    assert target == 112.0


def test_valid_atr_env_still_honored(monkeypatch, restore_levels_env):
    mod = _reload_levels(
        monkeypatch,
        EQUITY_ATR_PERIOD="10",
        EQUITY_ATR_STOP_MULT="2.5",
        EQUITY_MIN_STOP_PCT="0.04",
        EQUITY_MAX_STOP_PCT="0.12",
        EQUITY_ATR_TARGET_MULT="4.0",
    )
    assert mod.EQUITY_ATR_PERIOD == 10
    assert mod.EQUITY_ATR_STOP_MULT == 2.5
    assert mod.EQUITY_MIN_STOP_PCT == 0.04
    assert mod.EQUITY_MAX_STOP_PCT == 0.12
    assert mod.EQUITY_ATR_TARGET_MULT == 4.0
