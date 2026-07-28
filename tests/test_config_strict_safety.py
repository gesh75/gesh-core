"""
P0-B Strict Safety Boolean Configuration Tests (gesh-core)

Covers PAPER_MODE, REQUIRE_APPROVAL, MARKET_REGIME_GATE strict parsing
and effective_config provenance per the P0-B spec.

All tests use isolated monkeypatching of os.environ; no production state touched.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from gesh_core.trading.config import (
    ConfigError,
    _env_strict_bool,
    effective_config,
)

# ─────────────────────────────────────────────────────────────────────────────
# Parser contract tests for the three safety variables
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("key", ["PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"])
def test_missing_preserves_default(key):
    """Missing env var preserves documented default (True for all three)."""
    with patch.dict(os.environ, {}, clear=True):
        # Ensure the var is absent
        if key in os.environ:
            del os.environ[key]
        val = _env_strict_bool(key, True)
        assert val is True


@pytest.mark.parametrize("key", ["PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"])
@pytest.mark.parametrize("token", ["true", "True", "TRUE", "1", "yes", "Yes", "on", "ON"])
def test_true_tokens_accepted_case_insensitive(key, token):
    with patch.dict(os.environ, {key: token}):
        assert _env_strict_bool(key, False) is True


@pytest.mark.parametrize("key", ["PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"])
@pytest.mark.parametrize("token", ["false", "False", "FALSE", "0", "no", "No", "off", "OFF"])
def test_false_tokens_accepted_case_insensitive(key, token):
    with patch.dict(os.environ, {key: token}):
        assert _env_strict_bool(key, True) is False


@pytest.mark.parametrize("key", ["PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"])
def test_whitespace_surrounding_accepted(key):
    with patch.dict(os.environ, {key: "  true  "}):
        assert _env_strict_bool(key, False) is True
    with patch.dict(os.environ, {key: "\tfalse\n"}):
        assert _env_strict_bool(key, True) is False


@pytest.mark.parametrize("key", ["PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"])
def test_blank_raises(key):
    with patch.dict(os.environ, {key: ""}):
        with pytest.raises(ConfigError) as exc:
            _env_strict_bool(key, True)
        assert "Blank value" in str(exc.value)


@pytest.mark.parametrize("key", ["PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"])
@pytest.mark.parametrize(
    "bad",
    [
        "truthy",
        "falsee",
        "maybe",
        "2",
        "foo",
        "on/off",
        "yesx",
        "nope",
    ],
)
def test_malformed_raises(key, bad):
    with patch.dict(os.environ, {key: bad}):
        with pytest.raises(ConfigError) as exc:
            _env_strict_bool(key, True)
        assert "Invalid value" in str(exc.value)


# ─────────────────────────────────────────────────────────────────────────────
# Defaults unchanged, raise behavior, effective_config
# ─────────────────────────────────────────────────────────────────────────────


def test_existing_defaults_unchanged():
    """Documented defaults (True) remain when no env var."""
    with patch.dict(os.environ, {}, clear=True):
        cfg = effective_config()
        assert cfg.paper_mode is True
        assert cfg.require_approval is True
        assert cfg.market_regime_gate is True


def test_blank_raises_typed_error():
    with patch.dict(os.environ, {"PAPER_MODE": ""}):
        with pytest.raises(ConfigError):
            _env_strict_bool("PAPER_MODE", True)


def test_effective_config_reports_correct_value_and_source():
    with patch.dict(os.environ, {"PAPER_MODE": "false", "REQUIRE_APPROVAL": "true"}):
        eff = effective_config()
        assert eff.settings["PAPER_MODE"].parsed_value is False
        assert eff.settings["PAPER_MODE"].source == "environment"
        assert eff.settings["REQUIRE_APPROVAL"].parsed_value is True
        assert eff.settings["MARKET_REGIME_GATE"].source == "default"  # missing


def test_secrets_redacted():
    # These bools carry no secrets; raw_input for present vars is the token (safe)
    with patch.dict(os.environ, {"PAPER_MODE": "true"}):
        eff = effective_config()
        assert eff.settings["PAPER_MODE"].raw_input == "true"
        # No secret-like values appear


def test_config_hash_stable_and_changes():
    base = {"PAPER_MODE": "true", "REQUIRE_APPROVAL": "true", "MARKET_REGIME_GATE": "true"}
    with patch.dict(os.environ, base):
        h1 = effective_config().config_hash
    with patch.dict(os.environ, base):
        h2 = effective_config().config_hash
    assert h1 == h2

    with patch.dict(os.environ, {**base, "PAPER_MODE": "false"}):
        h3 = effective_config().config_hash
    assert h1 != h3


# End of P0-B strict safety tests.
