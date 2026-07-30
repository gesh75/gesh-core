"""
P0-B Strict Safety Boolean Configuration Tests (gesh-core)

Covers PAPER_MODE, REQUIRE_APPROVAL, MARKET_REGIME_GATE strict parsing
and effective_config provenance per the P0-B spec.

All tests use isolated monkeypatching of os.environ; no production state touched.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from gesh_core.trading.config import (
    ConfigError,
    _env_strict_bool,
    effective_config,
    load_risk_config,
)


@pytest.fixture(autouse=True)
def clear_safety_env(monkeypatch):
    """Remove safety variables for each test and restore inherited values afterward."""
    for key in ("PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"):
        monkeypatch.delenv(key, raising=False)


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
@pytest.mark.parametrize("token", ["true", "True", "TRUE", " true ", "\tTRUE\n"])
def test_true_tokens_accepted_case_insensitive(key, token):
    with patch.dict(os.environ, {key: token}):
        assert _env_strict_bool(key, False) is True


@pytest.mark.parametrize("key", ["PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"])
@pytest.mark.parametrize("token", ["false", "False", "FALSE", " false ", "\tFALSE\n"])
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
# Defaults unchanged, raise behavior, effective_config, parity, redaction, immutability
# ─────────────────────────────────────────────────────────────────────────────


def test_existing_defaults_unchanged():
    """Documented defaults (True) remain when no env var (autouse fixture ensures hermetic)."""
    cfg = effective_config()
    assert cfg.paper_mode is True
    assert cfg.require_approval is True
    assert cfg.market_regime_gate is True


@pytest.mark.parametrize("key", ["PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"])
def test_legacy_aliases_raise(key):
    """Every legacy alias (1/0, yes/no, y/n, on/off) is malformed and raises."""
    for bad in ("1", "0", "yes", "no", "y", "n", "on", "off", "Yes", "ON"):
        with patch.dict(os.environ, {key: bad}):
            with pytest.raises(ConfigError):
                _env_strict_bool(key, True)
            with pytest.raises(ConfigError):
                load_risk_config()
            with pytest.raises(ConfigError):
                effective_config()


def test_blank_raises_typed_error_for_both_parsers():
    """Blank causes both load_risk_config() and effective_config() to raise ConfigError."""
    with patch.dict(os.environ, {"PAPER_MODE": ""}):
        with pytest.raises(ConfigError):
            _env_strict_bool("PAPER_MODE", True)
        with pytest.raises(ConfigError):
            load_risk_config()
        with pytest.raises(ConfigError):
            effective_config()


def test_malformed_raises_for_both_parsers():
    """Malformed causes both parsers to raise ConfigError (parity)."""
    with patch.dict(os.environ, {"REQUIRE_APPROVAL": "maybe"}):
        with pytest.raises(ConfigError):
            load_risk_config()
        with pytest.raises(ConfigError):
            effective_config()


@pytest.mark.parametrize("key", ["PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"])
@pytest.mark.parametrize("bad", ["MALFORMED_SENTINEL_42", "garbage", "1"])
def test_malformed_value_never_in_exception_message(key, bad):
    """Malformed input must not appear in any ConfigError message (redaction)."""
    with patch.dict(os.environ, {key: bad}):
        for func in (_env_strict_bool, load_risk_config, effective_config):
            with pytest.raises(ConfigError) as exc:
                if func is _env_strict_bool:
                    func(key, True)
                else:
                    func()
            assert bad not in str(exc.value)
            assert "expected 'true' or 'false'" in str(exc.value) or "Blank value" in str(exc.value)


@pytest.mark.parametrize("key", ["PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"])
def test_public_path_coverage_blank_malformed_legacy_redacted_missing(key):
    """Full public-path coverage across all three vars for blank/malformed/legacy/ provenance/ redaction."""
    # blank → raises for both
    with patch.dict(os.environ, {key: ""}):
        with pytest.raises(ConfigError):
            load_risk_config()
        with pytest.raises(ConfigError):
            effective_config()

    # malformed → raises for both
    with patch.dict(os.environ, {key: "MALFORMED_X"}):
        with pytest.raises(ConfigError):
            load_risk_config()
        with pytest.raises(ConfigError):
            effective_config()
        with pytest.raises(ConfigError):
            _env_strict_bool(key, True)

    # legacy aliases → raise for both
    for legacy in ("1", "0", "yes", "no", "on", "off"):
        with patch.dict(os.environ, {key: legacy}):
            with pytest.raises(ConfigError):
                load_risk_config()
            with pytest.raises(ConfigError):
                effective_config()

    # valid present → <redacted>
    with patch.dict(os.environ, {key: "true"}):
        eff = effective_config()
        assert eff.settings[key].raw_input == "<redacted>"
        assert eff.settings[key].source == "environment"

    # missing → <missing>
    # (fixture ensures absent)
    eff2 = effective_config()
    assert eff2.settings[key].raw_input == "<missing>"
    assert eff2.settings[key].source == "default"

    # exception strings never contain raw input (already asserted in redaction test)


def test_effective_config_reports_correct_value_and_source():
    with patch.dict(os.environ, {"PAPER_MODE": "false", "REQUIRE_APPROVAL": "true"}):
        eff = effective_config()
        assert eff.settings["PAPER_MODE"].parsed_value is False
        assert eff.settings["PAPER_MODE"].source == "environment"
        assert eff.settings["REQUIRE_APPROVAL"].parsed_value is True
        assert eff.settings["MARKET_REGIME_GATE"].source == "default"  # missing


def test_raw_input_redacted_or_missing_never_original_token():
    """Present valid: <redacted>; missing: <missing>; never the original env token."""
    with patch.dict(os.environ, {"PAPER_MODE": "true"}):
        eff = effective_config()
        assert eff.settings["PAPER_MODE"].raw_input == "<redacted>"
        assert eff.settings["PAPER_MODE"].raw_input != "true"
    # missing case
    eff2 = effective_config()
    assert eff2.settings["PAPER_MODE"].raw_input == "<missing>"


def test_config_hash_stable_and_sensitivity():
    """Hash semantics per final owner ruling: canonical components retained; spelling variants same hash; missing vs explicit differ by provenance; boolean change affects hash; stable across calls (resolved_at irrelevant)."""
    # true spelling variants produce identical hash
    true_variants = [
        {"PAPER_MODE": "true", "REQUIRE_APPROVAL": "true", "MARKET_REGIME_GATE": "true"},
        {"PAPER_MODE": "True", "REQUIRE_APPROVAL": "TRUE", "MARKET_REGIME_GATE": " true "},
        {"PAPER_MODE": "TRUE", "REQUIRE_APPROVAL": "true", "MARKET_REGIME_GATE": "\tTrue\n"},
    ]
    hashes_true = []
    for env in true_variants:
        with patch.dict(os.environ, env):
            hashes_true.append(effective_config().config_hash)
    assert len(set(hashes_true)) == 1, "All explicit true spelling variants must share hash"

    # false spelling variants produce identical hash
    false_variants = [
        {"PAPER_MODE": "false", "REQUIRE_APPROVAL": "false", "MARKET_REGIME_GATE": "false"},
        {"PAPER_MODE": "False", "REQUIRE_APPROVAL": "FALSE", "MARKET_REGIME_GATE": " false "},
        {"PAPER_MODE": "FALSE", "REQUIRE_APPROVAL": "false", "MARKET_REGIME_GATE": "\tFalse\n"},
    ]
    hashes_false = []
    for env in false_variants:
        with patch.dict(os.environ, env):
            hashes_false.append(effective_config().config_hash)
    assert len(set(hashes_false)) == 1, "All explicit false spelling variants must share hash"

    # missing default True vs explicit env true → different hashes (provenance differs)
    with patch.dict(os.environ, {}, clear=True):
        h_missing = effective_config().config_hash
    with patch.dict(
        os.environ, {"PAPER_MODE": "true", "REQUIRE_APPROVAL": "true", "MARKET_REGIME_GATE": "true"}
    ):
        h_explicit = effective_config().config_hash
    assert h_missing != h_explicit, "Missing default vs explicit true must differ (provenance)"

    # changing any of the three resolved booleans changes the hash
    base = {"PAPER_MODE": "true", "REQUIRE_APPROVAL": "true", "MARKET_REGIME_GATE": "true"}
    with patch.dict(os.environ, base):
        h_base = effective_config().config_hash
    for k in base:
        changed = {**base, k: "false"}
        with patch.dict(os.environ, changed):
            assert effective_config().config_hash != h_base, f"Hash must change when {k} flips"

    # two calls under unchanged configuration have same hash regardless of resolved_at
    with patch.dict(os.environ, base):
        eff1 = effective_config()
        eff2 = effective_config()
        assert eff1.config_hash == eff2.config_hash
        # resolved_at may differ but must not affect hash (no timestamp in canonical)


def test_settings_collection_is_immutable():
    """The settings collection cannot be mutated after construction."""
    eff = effective_config()
    with pytest.raises(TypeError):
        eff.settings["PAPER_MODE"] = eff.settings["PAPER_MODE"]  # type: ignore[index]
    with pytest.raises(TypeError):
        del eff.settings["PAPER_MODE"]  # type: ignore[attr-defined]


def test_no_environment_side_effects(monkeypatch):
    """Calling load_risk_config / effective_config must not mutate os.environ."""
    # Set explicit valid values
    monkeypatch.setenv("PAPER_MODE", "true")
    monkeypatch.setenv("REQUIRE_APPROVAL", "false")
    monkeypatch.setenv("MARKET_REGIME_GATE", "true")

    before = dict(os.environ)

    _ = load_risk_config()
    _ = effective_config()

    after = dict(os.environ)
    assert after == before, "os.environ must be unchanged after config calls"


def test_exact_public_output_and_frozen_regression():
    """Regression coverage for mixed config, independent hash oracle, and FrozenInstanceError."""
    with patch.dict(os.environ, {"PAPER_MODE": "false", "REQUIRE_APPROVAL": "true"}):
        # load_risk_config top-level values
        cfg = load_risk_config()
        assert cfg.paper_mode is False
        assert cfg.require_approval is True
        assert cfg.market_regime_gate is True

        # effective_config top-level values
        eff = effective_config()
        assert eff.paper_mode is False
        assert eff.require_approval is True
        assert eff.market_regime_gate is True

        # exact metadata for all three
        pm = eff.settings["PAPER_MODE"]
        assert pm.parsed_value is False
        assert pm.source == "environment"
        assert pm.raw_input == "<redacted>"
        assert pm.validation_status == "valid"
        assert pm.name == "PAPER_MODE"

        ra = eff.settings["REQUIRE_APPROVAL"]
        assert ra.parsed_value is True
        assert ra.source == "environment"
        assert ra.raw_input == "<redacted>"
        assert ra.validation_status == "valid"
        assert ra.name == "REQUIRE_APPROVAL"

        mrg = eff.settings["MARKET_REGIME_GATE"]
        assert mrg.parsed_value is True
        assert mrg.source == "default"
        assert mrg.raw_input == "<missing>"
        assert mrg.validation_status == "missing"
        assert mrg.name == "MARKET_REGIME_GATE"

        # independent exact hash oracle (constructed manually, not derived from eff.settings)
        canonical = (
            "MARKET_REGIME_GATE:default:True:missing|"
            "PAPER_MODE:environment:False:valid|"
            "REQUIRE_APPROVAL:environment:True:valid"
        )
        expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert eff.config_hash == expected_hash

    # Complementary configuration: in the block above require_approval and
    # market_regime_gate are BOTH True, so a cross-wire between exactly those two
    # top-level fields survives. Three booleans cannot be pairwise distinct in one
    # configuration (pigeonhole), and MARKET_REGIME_GATE must be missing there for
    # the <missing>/default/missing metadata assertions. A second configuration
    # separates them and closes the gap.
    with patch.dict(os.environ, {"PAPER_MODE": "true", "REQUIRE_APPROVAL": "false"}):
        eff_b = effective_config()
        assert eff_b.paper_mode is True
        assert eff_b.require_approval is False
        assert eff_b.market_regime_gate is True
        assert eff_b.settings["PAPER_MODE"].parsed_value is True
        assert eff_b.settings["REQUIRE_APPROVAL"].parsed_value is False
        assert eff_b.settings["MARKET_REGIME_GATE"].parsed_value is True

    # Identity semantics: two reads of an UNCHANGED configuration compare equal
    # and hash equal; resolved_at is excluded from both.
    with patch.dict(os.environ, {"PAPER_MODE": "false", "REQUIRE_APPROVAL": "true"}):
        first = effective_config()
        second = effective_config()
        assert first == second, "unchanged configuration must compare equal"
        assert hash(first) == hash(second), "EffectiveConfig must be hashable"
        assert len({first, second}) == 1
        assert first.config_hash == second.config_hash

    # FrozenInstanceError regression on EffectiveConfig (and its inner settings)
    with patch.dict(os.environ, {}):
        eff2 = effective_config()
        with pytest.raises(FrozenInstanceError):
            eff2.paper_mode = True  # type: ignore[attr-defined]
        with pytest.raises(FrozenInstanceError):
            eff2.settings["PAPER_MODE"].parsed_value = True  # type: ignore[index]


# End of P0-B strict safety tests.
