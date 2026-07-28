"""
trading/config.py — risk + mode configuration.

All values overridable via environment variables. Defaults are
ULTRA-CONSERVATIVE on purpose — paper mode, low caps, high confidence floor.
Flip PAPER_MODE=false ONLY after weeks of clean paper runs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_float(key: str, default: float) -> float:
    # Empty-string env (common in launchd plists / .env) falls back to default,
    # not a ValueError (product's more-robust parsing, now shared).
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


class ConfigError(ValueError):
    """Typed error raised for invalid safety-critical boolean configuration.

    Blank or malformed values for PAPER_MODE, REQUIRE_APPROVAL, or
    MARKET_REGIME_GATE must fail construction with this error rather than
    silently coercing to False.
    """


def _env_strict_bool(key: str, default: bool) -> bool:
    """Strict parser for safety-critical booleans.

    - Missing env var: return documented default (no change to defaults).
    - Valid tokens (case-insensitive after strip): true/false accepted.
    - Blank (after strip): invalid, raise ConfigError.
    - Any other token: invalid, raise ConfigError.
    - Never silently returns False for bad input.
    """
    raw = os.getenv(key)
    if raw is None:
        return default
    stripped = raw.strip()
    if stripped == "":
        raise ConfigError(
            f"Blank value for {key} is invalid (safety-critical boolean requires explicit true/false or omission)"
        )
    lowered = stripped.lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    raise ConfigError(
        f"Invalid value for {key}: {raw!r} (expected true/false token, blank, or omission)"
    )


@dataclass(frozen=True)
class RiskConfig:
    # --- mode ---
    paper_mode: bool = True
    require_approval: bool = True       # every intent waits for explicit approval before live
    kill_switch_path: str = str(Path.home() / ".gesh" / "KILL")

    # --- caps ---
    max_position_pct: float = 0.02      # 2% of equity per symbol
    max_daily_loss_pct: float = 0.01    # 1% of equity per day
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
    max_price_age_seconds: int = 300    # LIVE: reject if last quote > 5 min old
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
    max_sector_pct: float = 0.40        # reject if any single sector > 40% of portfolio
    earnings_proximity_hours: int = 48  # block BUY within N hours of earnings
    max_consecutive_loss_days: int = 3  # auto-suspend after N straight loss days
    min_confidence_risk_off: float = 0.85  # raised confidence floor when macro is RISK_OFF
    # Market-regime AVOID gate: block NEW longs when SPY is below its trailing
    # 200-day MA (or macro is RISK_OFF). Backtest-validated 2026-06-14 — turned
    # the only alpha-negative walk-forward fold (2022 bear) positive and lifted
    # mean alpha +42% (docs/SIGNAL_PROFITABILITY_2026-06.md). ON by default;
    # set MARKET_REGIME_GATE=0 to disable. Fail-open on SPY-data error.
    market_regime_gate: bool = True
    market_regime_ma_days: int = 200


def load_risk_config() -> RiskConfig:
    """Build RiskConfig from environment, falling back to ultra-conservative defaults."""
    return RiskConfig(
        paper_mode=_env_strict_bool("PAPER_MODE", True),
        require_approval=_env_strict_bool("REQUIRE_APPROVAL", True),
        kill_switch_path=os.getenv("KILL_SWITCH_PATH", str(Path.home() / ".gesh" / "KILL")),
        max_position_pct=_env_float("MAX_POSITION_PCT", 0.02),
        max_daily_loss_pct=_env_float("MAX_DAILY_LOSS_PCT", 0.01),
        max_orders_per_day=_env_int("MAX_ORDERS_PER_DAY", 3),
        min_cash_buffer_usd=_env_float("MIN_CASH_BUFFER_USD", 500.0),
        min_confidence=_env_float("MIN_CONFIDENCE", 0.75),
        min_entry_score=_env_float("MIN_ENTRY_SCORE", 0.35),
        paper_cash_usd=_env_float("PAPER_CASH_USD", 100_000.0),
        max_price_age_seconds=_env_int("MAX_PRICE_AGE_SECONDS", 300),
        max_price_age_seconds_paper=_env_int("MAX_PRICE_AGE_SECONDS_PAPER", 1800),
        market_open_hhmm=os.getenv("MARKET_OPEN_HHMM", "09:30"),
        market_close_hhmm=os.getenv("MARKET_CLOSE_HHMM", "16:00"),
        market_timezone=os.getenv("MARKET_TIMEZONE", "America/New_York"),
        max_sector_pct=_env_float("MAX_SECTOR_PCT", 0.40),
        earnings_proximity_hours=_env_int("EARNINGS_PROXIMITY_HOURS", 48),
        max_consecutive_loss_days=_env_int("MAX_CONSECUTIVE_LOSS_DAYS", 3),
        min_confidence_risk_off=_env_float("MIN_CONFIDENCE_RISK_OFF", 0.85),
        market_regime_gate=_env_strict_bool("MARKET_REGIME_GATE", True),
        market_regime_ma_days=_env_int("MARKET_REGIME_MA_DAYS", 200),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Effective configuration provenance (P0-B)
# Read-only, no mutation side effects, secrets redacted, deterministic hash.
# ─────────────────────────────────────────────────────────────────────────────

from dataclasses import dataclass, field
from typing import Literal, Any
import hashlib


@dataclass(frozen=True)
class ConfigSetting:
    name: str
    parsed_value: Any
    source: Literal["default", "environment"]
    raw_input: str  # redacted for secrets (none for these safety bools)
    validation_status: Literal["valid", "invalid", "missing", "blank"]


@dataclass(frozen=True)
class EffectiveConfig:
    settings: dict[str, ConfigSetting] = field(default_factory=dict)
    config_hash: str = ""
    resolved_at: str = ""
    # Safety-relevant only for this patch
    paper_mode: bool = True
    require_approval: bool = True
    market_regime_gate: bool = True


def effective_config() -> EffectiveConfig:
    """Return read-only effective configuration for safety-relevant settings.

    Source is "default" when env var missing, "environment" when present.
    Raw input is the env value (these are booleans; no secret redaction needed).
    Validation status reflects strict parser outcome.
    Hash is deterministic SHA-256 over sorted name+source+parsed+status.
    No side effects, no mutation.
    """
    from datetime import datetime, timezone
    settings: dict[str, ConfigSetting] = {}
    safety_keys = ["PAPER_MODE", "REQUIRE_APPROVAL", "MARKET_REGIME_GATE"]
    defaults = {"PAPER_MODE": True, "REQUIRE_APPROVAL": True, "MARKET_REGIME_GATE": True}

    for key in safety_keys:
        raw = os.getenv(key)
        if raw is None:
            parsed = defaults[key]
            source: Literal["default", "environment"] = "default"
            status: Literal["valid", "invalid", "missing", "blank"] = "missing"
            raw_redacted = "<missing>"
        else:
            stripped = raw.strip()
            source = "environment"
            if stripped == "":
                status = "blank"
                # For representation, we still record what the parser would do
                # but the construction would have raised; here we show the input
                parsed = defaults[key]
            else:
                try:
                    parsed = _env_strict_bool(key, defaults[key])
                    status = "valid"
                except ConfigError:
                    status = "invalid"
                    parsed = defaults[key]
            raw_redacted = stripped  # bools carry no secrets

        settings[key] = ConfigSetting(
            name=key,
            parsed_value=parsed,
            source=source,
            raw_input=raw_redacted,
            validation_status=status,
        )

    # Deterministic hash over canonical form (sorted keys, no timestamps)
    canonical = "|".join(
        f"{k}:{v.source}:{v.parsed_value}:{v.validation_status}"
        for k, v in sorted(settings.items())
    )
    h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return EffectiveConfig(
        settings=settings,
        config_hash=h,
        resolved_at=datetime.now(timezone.utc).isoformat(),
        paper_mode=settings["PAPER_MODE"].parsed_value,
        require_approval=settings["REQUIRE_APPROVAL"].parsed_value,
        market_regime_gate=settings["MARKET_REGIME_GATE"].parsed_value,
    )
