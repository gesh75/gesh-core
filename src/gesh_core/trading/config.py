"""
trading/config.py — risk + mode configuration.

All values overridable via environment variables. Defaults are
ULTRA-CONSERVATIVE on purpose — paper mode, low caps, high confidence floor.
Flip PAPER_MODE=false ONLY after weeks of clean paper runs.
"""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Literal


class ConfigError(ValueError):
    """Typed error raised for invalid safety-critical configuration.

    Blank or malformed values for PAPER_MODE, REQUIRE_APPROVAL, or
    MARKET_REGIME_GATE must fail construction with this error rather than
    silently coercing to False.

    NaN, infinity, negative caps, out-of-range, and malformed numeric
    settings must fail construction rather than silently disabling gates.
    Exception messages name the key and the rule; they never echo the
    supplied raw value.
    """


def _parse_strict_bool(key: str, raw: str | None, default: bool) -> bool:
    """Pure strict parser for safety-critical booleans.

    Captured raw value is used for both provenance and parsing decision.
    Missing: default. Blank: ConfigError (no raw exposure). Malformed: ConfigError
    identifying key and syntax without echoing supplied value.
    """
    if raw is None:
        return default
    stripped = raw.strip()
    if stripped == "":
        raise ConfigError(
            f"Blank value for {key} is invalid (safety-critical boolean requires explicit true/false or omission)"
        )
    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ConfigError(
        f"Invalid value for {key}; expected 'true' or 'false' after trimming, "
        "or unset the variable to use its default"
    )


def _env_strict_bool(key: str, default: bool) -> bool:
    """Strict parser for safety-critical booleans (public contract unchanged).

    Delegates to _parse_strict_bool after single os.getenv capture.
    """
    return _parse_strict_bool(key, os.getenv(key), default)


@dataclass(frozen=True)
class NumericSpec:
    key: str
    kind: Literal["float", "int"]
    default: float | int
    minimum: float | None = None
    maximum: float | None = None
    allow_zero: bool = True
    attr: str | None = None


# Field-specific numeric safety limits. Empty/missing env keeps the default.
# Zero validity is explicit per key (allow_zero).
NUMERIC_SPECS: tuple[NumericSpec, ...] = (
    NumericSpec("MAX_POSITION_PCT", "float", 0.02, 0.0, 1.0, True, "max_position_pct"),
    NumericSpec("MAX_DAILY_LOSS_PCT", "float", 0.01, 0.0, 1.0, False, "max_daily_loss_pct"),
    NumericSpec("MAX_ORDERS_PER_DAY", "int", 3, 1.0, None, False, "max_orders_per_day"),
    NumericSpec("MIN_CASH_BUFFER_USD", "float", 500.0, 0.0, None, True, "min_cash_buffer_usd"),
    NumericSpec("MIN_CONFIDENCE", "float", 0.75, 0.0, 1.0, True, "min_confidence"),
    NumericSpec("MIN_ENTRY_SCORE", "float", 0.35, 0.0, 1.0, True, "min_entry_score"),
    NumericSpec("PAPER_CASH_USD", "float", 100_000.0, 0.0, None, False, "paper_cash_usd"),
    NumericSpec("MAX_PRICE_AGE_SECONDS", "int", 300, 1.0, None, False, "max_price_age_seconds"),
    NumericSpec(
        "MAX_PRICE_AGE_SECONDS_PAPER",
        "int",
        1800,
        1.0,
        None,
        False,
        "max_price_age_seconds_paper",
    ),
    NumericSpec("MAX_SECTOR_PCT", "float", 0.40, 0.0, 1.0, True, "max_sector_pct"),
    NumericSpec("EARNINGS_PROXIMITY_HOURS", "int", 48, 0.0, None, True, "earnings_proximity_hours"),
    NumericSpec(
        "MAX_CONSECUTIVE_LOSS_DAYS",
        "int",
        3,
        1.0,
        None,
        False,
        "max_consecutive_loss_days",
    ),
    NumericSpec(
        "MIN_CONFIDENCE_RISK_OFF",
        "float",
        0.85,
        0.0,
        1.0,
        True,
        "min_confidence_risk_off",
    ),
    NumericSpec("MARKET_REGIME_MA_DAYS", "int", 200, 1.0, None, False, "market_regime_ma_days"),
    NumericSpec("KELLY_MAX_POSITION_PCT", "float", 0.25, 0.0, 1.0, True, None),
    NumericSpec("KELLY_MAX_GROSS_PCT", "float", 1.0, 0.0, 1.0, True, None),
)

_SPEC_BY_KEY: dict[str, NumericSpec] = {spec.key: spec for spec in NUMERIC_SPECS}


def _parse_int_token(key: str, token: str) -> int:
    body = token[1:] if token[:1] in "+-" else token
    if not body.isdigit():
        raise ConfigError(f"Invalid numeric value for {key}; expected a finite integer count")
    return int(token)


def _parse_numeric(
    spec: NumericSpec, raw: str | None
) -> tuple[float | int, Literal["default", "environment"], Literal["valid", "missing"]]:
    if raw is None or raw.strip() == "":
        return spec.default, "default", "missing"
    token = raw.strip()
    try:
        if spec.kind == "int":
            value: float | int = _parse_int_token(spec.key, token)
        else:
            value = float(token)
    except ConfigError:
        raise
    except (TypeError, ValueError):
        raise ConfigError(
            f"Invalid numeric value for {spec.key}; expected a finite {spec.kind}"
        ) from None
    if not math.isfinite(float(value)):
        raise ConfigError(f"Non-finite value for {spec.key} is invalid")
    if value == 0 and not spec.allow_zero:
        raise ConfigError(f"Zero is not a valid value for {spec.key}")
    if spec.minimum is not None and float(value) < spec.minimum:
        raise ConfigError(f"{spec.key} is below the minimum allowed value")
    if spec.maximum is not None and float(value) > spec.maximum:
        raise ConfigError(f"{spec.key} is above the maximum allowed value")
    if spec.kind == "float":
        value = float(value)
    return value, "environment", "valid"


def parse_unit_interval(key: str, raw: str | None, default: float) -> float:
    """Finite inclusive-[0, 1] cap. Empty/missing keeps ``default``; invalid raises."""
    base = _SPEC_BY_KEY.get(key)
    spec = NumericSpec(
        key,
        "float",
        default,
        0.0 if base is None else base.minimum,
        1.0 if base is None else base.maximum,
        True if base is None else base.allow_zero,
    )
    value, _, _ = _parse_numeric(spec, raw)
    return float(value)


def _resolved_numerics() -> dict[str, tuple[float | int, str, str]]:
    resolved: dict[str, tuple[float | int, str, str]] = {}
    for spec in NUMERIC_SPECS:
        resolved[spec.key] = _parse_numeric(spec, os.getenv(spec.key))
    return resolved


def _check_numeric_relationships(values: dict[str, float | int]) -> None:
    if float(values["MIN_CONFIDENCE_RISK_OFF"]) < float(values["MIN_CONFIDENCE"]):
        raise ConfigError("MIN_CONFIDENCE_RISK_OFF cannot be below MIN_CONFIDENCE")
    if int(values["MAX_PRICE_AGE_SECONDS_PAPER"]) < int(values["MAX_PRICE_AGE_SECONDS"]):
        raise ConfigError("MAX_PRICE_AGE_SECONDS_PAPER cannot be below MAX_PRICE_AGE_SECONDS")


@dataclass(frozen=True)
class RiskConfig:
    # --- mode ---
    paper_mode: bool = True
    require_approval: bool = True  # every intent waits for explicit approval before live
    kill_switch_path: str = str(Path.home() / ".gesh" / "KILL")

    # --- caps ---
    max_position_pct: float = 0.02  # 2% of equity per symbol
    max_daily_loss_pct: float = 0.01  # 1% of equity per day
    max_orders_per_day: int = 3
    min_cash_buffer_usd: float = 500.0
    min_confidence: float = 0.75
    # Entry-conviction floor on the consensus raw_score for NEW long entries
    # (portfolio path). confidence (active_nodes / total) is ≈1.0 in practice and a
    # weak quality lever; raw_score is the real conviction signal. 0.35 filters the
    # weakest BUYs (verdict BUY fires at ≥0.25) while keeping solid BUYs + STRONG BUYs
    # (≥0.55), preserving entry velocity toward the n=30 autonomy gate. Entries only —
    # never gates SELL/exit. Env MIN_ENTRY_SCORE; set 0.0 to disable, 0.55 for
    # STRONG-BUY-only. (2026-06-21, P2 entry conviction.)
    min_entry_score: float = 0.35
    # Simulated cash balance used by the CASH_FLOOR gate in PAPER mode only, so paper
    # trades aren't blocked by the real (often near-empty, fully-invested) account
    # balance. In LIVE mode the real account cash is used instead. (Mirrors the
    # $100k Alpaca paper convention.)
    paper_cash_usd: float = 100_000.0

    # --- data freshness / hours ---
    max_price_age_seconds: int = 300  # LIVE: reject if last quote > 5 min old
    # PAPER: the daily chain's snapshot is fetched at step 1 but the gate runs
    # after engines + the Claude call (5-13 min later under Yahoo throttle), so a
    # 300s limit rejected every chain trade on its own pipeline latency, not on
    # actually-stale data (daily-bar paper signals tolerate minutes-old quotes).
    # 30 min still rejects a genuinely stale snapshot (prior day / hung fetch).
    # Mode-aware like the paper CASH_FLOOR/DAILY_LOSS gates (#32/#36); LIVE
    # keeps the tight 300s.
    max_price_age_seconds_paper: int = 1800
    market_open_hhmm: str = "09:30"
    market_close_hhmm: str = "16:00"
    market_timezone: str = "America/New_York"

    # --- additional safety gates ---
    max_sector_pct: float = 0.40  # reject if any single sector > 40% of portfolio
    earnings_proximity_hours: int = 48  # block BUY within N hours of earnings
    max_consecutive_loss_days: int = 3  # auto-suspend after N straight loss days
    min_confidence_risk_off: float = 0.85  # raised confidence floor when macro is RISK_OFF
    # Market-regime AVOID gate: block NEW longs when SPY is below its trailing
    # 200-day MA (or macro is RISK_OFF). Backtest-validated 2026-06-14 — turned
    # the only alpha-negative walk-forward fold (2022 bear) positive and lifted
    # mean alpha +42% (docs/SIGNAL_PROFITABILITY_2026-06.md). ON by default;
    # set MARKET_REGIME_GATE=false to disable. Fail-open on SPY-data error.
    market_regime_gate: bool = True
    market_regime_ma_days: int = 200


def load_risk_config() -> RiskConfig:
    """Build RiskConfig from environment, falling back to ultra-conservative defaults."""
    numerics = _resolved_numerics()
    _check_numeric_relationships({key: triple[0] for key, triple in numerics.items()})
    kwargs: dict[str, object] = {}
    for spec in NUMERIC_SPECS:
        if spec.attr:
            kwargs[spec.attr] = numerics[spec.key][0]
    return RiskConfig(
        paper_mode=_env_strict_bool("PAPER_MODE", True),
        require_approval=_env_strict_bool("REQUIRE_APPROVAL", True),
        kill_switch_path=os.getenv("KILL_SWITCH_PATH", str(Path.home() / ".gesh" / "KILL")),
        market_open_hhmm=os.getenv("MARKET_OPEN_HHMM", "09:30"),
        market_close_hhmm=os.getenv("MARKET_CLOSE_HHMM", "16:00"),
        market_timezone=os.getenv("MARKET_TIMEZONE", "America/New_York"),
        market_regime_gate=_env_strict_bool("MARKET_REGIME_GATE", True),
        **kwargs,  # type: ignore[arg-type]
    )


# ─────────────────────────────────────────────────────────────────────────────
# Effective configuration provenance (P0-B)
# Read-only, no mutation side effects, secrets redacted, deterministic hash.
# ─────────────────────────────────────────────────────────────────────────────


def _canon_parsed(value: bool | int | float) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    return format(float(value), ".15g")


@dataclass(frozen=True)
class ConfigSetting:
    name: str
    parsed_value: bool | int | float
    source: Literal["default", "environment"]
    raw_input: str
    validation_status: Literal["valid", "missing"]


@dataclass(frozen=True)
class EffectiveConfig:
    # hash=False: the mapping is a MappingProxyType over a dict and is therefore
    # unhashable, which made the whole frozen dataclass unhashable even though
    # frozen=True advertises the opposite. It stays in __eq__ (mapping equality
    # works fine); config_hash already encodes it for identity purposes.
    settings: MappingProxyType[str, ConfigSetting] = field(
        default_factory=lambda: MappingProxyType({}), hash=False
    )
    config_hash: str = ""
    # compare=False: resolved_at is a fresh timestamp on every call, so including
    # it in __eq__ meant two reads of an UNCHANGED configuration never compared
    # equal — a permanent false positive for any "did the config change?" check.
    # It is excluded from config_hash for the same reason.
    resolved_at: str = field(default="", compare=False)
    # Safety-relevant only for this patch
    paper_mode: bool = True
    require_approval: bool = True
    market_regime_gate: bool = True


def effective_config() -> EffectiveConfig:
    """Return read-only effective configuration for safety-relevant settings.

    Uses the same strict parsers as load_risk_config().
    Missing: default value, source="default", raw_input="<missing>", status="missing".
    Present valid: resolved value, source="environment", raw_input="<redacted>", status="valid".
    Blank or malformed: ConfigError propagates (no default substitution).
    Raw environment input is never exposed (only <missing> or <redacted>).
    Hash (config_hash) is deterministic SHA-256 over sorted name+source+parsed+status;
    resolved_at excluded. Numeric limits and provenance are part of the hash.
    Settings collection is immutable (MappingProxyType).
    No side effects, no mutation after construction.
    """
    settings_dict: dict[str, ConfigSetting] = {}
    safety_keys = ["PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"]
    defaults = {"PAPER_MODE": True, "REQUIRE_APPROVAL": True, "MARKET_REGIME_GATE": True}

    for key in safety_keys:
        raw = os.getenv(key)
        if raw is None:
            parsed: bool | int | float = defaults[key]
            source: Literal["default", "environment"] = "default"
            status: Literal["valid", "missing"] = "missing"
            raw_redacted = "<missing>"
        else:
            parsed = _parse_strict_bool(key, raw, defaults[key])
            source = "environment"
            status = "valid"
            raw_redacted = "<redacted>"

        settings_dict[key] = ConfigSetting(
            name=key,
            parsed_value=parsed,
            source=source,
            raw_input=raw_redacted,
            validation_status=status,
        )

    numerics = _resolved_numerics()
    _check_numeric_relationships({key: triple[0] for key, triple in numerics.items()})
    for key, (num_parsed, num_source, num_status) in numerics.items():
        settings_dict[key] = ConfigSetting(
            name=key,
            parsed_value=num_parsed,
            source=num_source,  # type: ignore[arg-type]
            raw_input="<missing>" if num_status == "missing" else "<redacted>",
            validation_status=num_status,  # type: ignore[arg-type]
        )

    canonical = "|".join(
        f"{k}:{v.source}:{_canon_parsed(v.parsed_value)}:{v.validation_status}"
        for k, v in sorted(settings_dict.items())
    )
    h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    immutable_settings = MappingProxyType(settings_dict)
    return EffectiveConfig(
        settings=immutable_settings,
        config_hash=h,
        resolved_at=datetime.now(UTC).isoformat(),
        paper_mode=bool(immutable_settings["PAPER_MODE"].parsed_value),
        require_approval=bool(immutable_settings["REQUIRE_APPROVAL"].parsed_value),
        market_regime_gate=bool(immutable_settings["MARKET_REGIME_GATE"].parsed_value),
    )
