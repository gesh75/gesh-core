"""
allocation_config.py — Buying Power Allocation & Scanner Settings

Mirrors the Trading Hub config panel:
  - Buying power allocation (stocks vs options)
  - Max $ per trade, max open positions
  - Scanner price/volume filters
  - Auto-trade gate (ON/OFF)
  - Extended hours trading flag
  - Scanner timeframe mode (daily / 1HR / 5MIN / premarket)

Stored in: gesh_config.json (project root)
All settings persist between sessions.

Usage:
    from allocation_config import load_config, save_config, validate_action

    cfg = load_config()
    ok, reason = validate_action("BUY", "NVDA", trade_usd=3500, open_positions=2)

gesh-core note (Phase 3.1)
--------------------------
This module is shared by the engine and product repos, which keep SEPARATE
``gesh_config.json`` files at their respective roots. Because it now lives
inside the installed ``gesh_core`` package, the config path can no longer be
derived from ``__file__`` (that would point inside gesh-core). It is resolved
relative to the current working directory instead — both the servers and the
autopilot start from their repo root — with a ``GESH_CONFIG_PATH`` env override
for callers that run from elsewhere.
"""

from __future__ import annotations

import json
import logging
import math
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gesh_core.trading.config import ConfigError

logger = logging.getLogger(__name__)


def _config_path() -> Path:
    """Resolve the active gesh_config.json.

    Order: ``GESH_CONFIG_PATH`` env override → ``<cwd>/gesh_config.json``.
    Resolved at call time so the correct per-repo config is used regardless of
    when this module was first imported.
    """
    override = os.getenv("GESH_CONFIG_PATH")
    if override:
        return Path(override)
    return Path.cwd() / "gesh_config.json"


# Back-compat module constant (no external code references it; kept so anything
# inspecting ``allocation_config.CONFIG_PATH`` still resolves to a real path).
CONFIG_PATH = _config_path()

# ─── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_CONFIG: dict[str, Any] = {
    # Buying power allocation
    "total_buying_power": None,  # set at runtime from Robinhood profile
    "stock_allocation_pct": 70.0,  # % of buying power for stocks
    "options_allocation_pct": 30.0,  # % of buying power for options
    # Per-trade hard caps
    "max_stock_per_trade": 5000.0,  # max $ on a single stock trade
    "max_options_per_trade": 2000.0,  # max $ on a single options trade
    "max_open_positions": 5,  # max simultaneous open positions
    "max_open_contracts": 3,  # max simultaneous open options contracts
    "min_cash_buffer": 500.0,  # never deploy below this cash level
    # Scanner filters
    "scanner_price_min": 0.10,  # min stock price for scanner
    "scanner_price_max": 10.00,  # max price ceiling — enforced ONLY in PRICE_CAPPED_MODES (penny universe)
    "scanner_volume_min": 200_000,  # min daily volume
    "scanner_timeframe": "daily",  # daily | 1HR | 5MIN | premarket | forex-1HR | forex-4HR
    # Execution gates
    "auto_trade": False,  # True = live execution enabled
    "extended_hours": True,  # pre-market & after-hours
    "paper_mode": False,  # True = all actions route to paper_trades
    # Portfolio screener universe
    "screener_universe": "default",  # default | aggressive | conservative | forex
    # Metadata
    "last_updated": None,
    "version": "1.1",
}

# Scanner modes where the scanner_price_max ceiling is meaningful (penny-stock
# universe). Intraday/forex modes intentionally have NO upper price cap.
PRICE_CAPPED_MODES = {"stock"}

# Canonical actions accepted by the execution gate. Rejecting rather than
# normalizing malformed actions keeps every safety check fail-closed.
TRADE_ACTIONS = frozenset({"BUY", "ADD", "TRIM", "SELL"})

LIVE_PERMISSION_REASON = "Auto-trade is OFF — review and execute manually"


@dataclass(frozen=True)
class ActionCheck:
    """Result of ``validate_action``.

    Iterates as ``(ok, reason)`` so ``ok, reason = validate_action(...)``
    keeps working. ``code`` is the structured decision; do not match
    free-text reasons in new callers.
    """

    ok: bool
    reason: str
    code: str = "OK"

    def __iter__(self) -> Iterator[object]:
        yield self.ok
        yield self.reason


# ─── Load / Save ──────────────────────────────────────────────────────────────


def _coerce_key(key: str, value: Any) -> tuple[Any, bool]:
    """Validate `value` against the type template in DEFAULT_CONFIG[key].

    Returns (usable_value, ok). On a type mismatch the SAFE default is returned
    with ok=False — critically, ``auto_trade`` (the live-execution gate) can
    never be enabled by a truthy non-bool like ``"yes"`` or ``1``, and numeric
    caps can never reach ``validate_action`` as strings (where ``trade_usd >
    "9999"`` raises TypeError inside the gate). bool is checked before int
    because bool subclasses int.
    """
    default = DEFAULT_CONFIG[key]
    if default is None:
        return value, True  # runtime-set keys (buying power, timestamp)
    if isinstance(default, bool):
        return (value, True) if isinstance(value, bool) else (default, False)
    if isinstance(default, int) and not isinstance(default, bool):
        if isinstance(value, bool) or not isinstance(value, int):
            return default, False
        return value, True
    if isinstance(default, float):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return default, False
        return float(value), True
    if isinstance(default, str):
        return (value, True) if isinstance(value, str) else (default, False)
    return value, True


_ALLOC_NON_NEGATIVE = frozenset(
    {
        "max_stock_per_trade",
        "max_options_per_trade",
        "min_cash_buffer",
        "scanner_price_min",
        "scanner_price_max",
        "scanner_volume_min",
        "stock_allocation_pct",
        "options_allocation_pct",
    }
)
_ALLOC_POSITIVE_INT = frozenset({"max_open_positions", "max_open_contracts"})
_ALLOC_PCT = frozenset({"stock_allocation_pct", "options_allocation_pct"})


def _validate_allocation_numeric(key: str, value: Any) -> None:
    default = DEFAULT_CONFIG.get(key)
    if default is None or isinstance(default, (bool, str)):
        return
    if isinstance(default, int) and not isinstance(default, bool):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"Invalid integer value for {key}")
        if key in _ALLOC_POSITIVE_INT and value < 1:
            raise ConfigError(f"{key} must be a positive integer")
        if value < 0:
            raise ConfigError(f"{key} cannot be negative")
        return
    if isinstance(default, float):
        try:
            fv = float(value)
        except (TypeError, ValueError):
            raise ConfigError(f"Invalid numeric value for {key}") from None
        if not math.isfinite(fv):
            raise ConfigError(f"Non-finite value for {key} is invalid")
        if key in _ALLOC_NON_NEGATIVE and fv < 0:
            raise ConfigError(f"{key} cannot be negative")
        if key in _ALLOC_PCT and fv > 100:
            raise ConfigError(f"{key} is above the maximum allowed value")


def _validate_allocation_relationships(cfg: dict[str, Any]) -> None:
    stock = cfg.get("stock_allocation_pct")
    options = cfg.get("options_allocation_pct")
    if stock is None or options is None:
        return
    try:
        stock_f = float(stock)
        options_f = float(options)
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            "stock_allocation_pct and options_allocation_pct must be finite numbers"
        ) from exc
    if not (math.isfinite(stock_f) and math.isfinite(options_f)):
        raise ConfigError(
            "stock_allocation_pct and options_allocation_pct must be finite numbers"
        )
    if abs(stock_f + options_f - 100.0) > 1e-6:
        raise ConfigError("stock_allocation_pct and options_allocation_pct must sum to 100")


def load_config() -> dict[str, Any]:
    """Load config from disk, merging with defaults for any missing keys.

    Numeric caps that are present but invalid (wrong type, NaN, infinity,
    negative, non-integer counts) fail construction with ConfigError rather
    than silently restoring a default. ``auto_trade`` still falls back to
    False on a type mismatch so a truthy non-bool cannot enable live
    execution. Unknown keys pass through for forward compatibility. A
    corrupt/unreadable file degrades to the defaults instead of raising;
    the corrupt file is left on disk for inspection.
    """
    config_path = _config_path()
    if not config_path.exists():
        return save_config(DEFAULT_CONFIG)

    try:
        with open(config_path) as f:
            stored = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("gesh_config.json unreadable at %s (%s) — using defaults", config_path, e)
        return DEFAULT_CONFIG.copy()

    cfg = DEFAULT_CONFIG.copy()
    for key, value in stored.items() if isinstance(stored, dict) else ():
        if key in DEFAULT_CONFIG:
            coerced, ok = _coerce_key(key, value)
            if not ok:
                default = DEFAULT_CONFIG[key]
                if isinstance(default, (int, float)) and not isinstance(default, bool):
                    raise ConfigError(
                        f"Invalid numeric value for {key}; expected a finite "
                        f"{type(default).__name__}"
                    )
                logger.warning(
                    "gesh_config.json: %r has invalid type %s — using default %r",
                    key,
                    type(value).__name__,
                    default,
                )
                cfg[key] = coerced
                continue
            _validate_allocation_numeric(key, coerced)
            cfg[key] = coerced
        else:
            cfg[key] = value  # forward-compat passthrough
    _validate_allocation_relationships(cfg)
    return cfg


def save_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Persist config to disk with timestamp; atomic write, input not mutated.

    Returns the saved copy (with ``last_updated`` stamped). The temp-file +
    os.replace dance means a concurrent reader can never observe a truncated
    JSON file, and the caller's dict — including the module-level
    DEFAULT_CONFIG — is never mutated in place.
    """
    out = dict(cfg)
    out["last_updated"] = datetime.now(UTC).isoformat()
    path = _config_path()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(out, indent=2))
    os.replace(tmp, path)
    return out


def update_config(**kwargs) -> dict[str, Any]:
    """
    Update specific config keys and save.

    Example:
        update_config(max_stock_per_trade=8000, auto_trade=False)
    """
    cfg = load_config()
    for key, value in kwargs.items():
        if key not in DEFAULT_CONFIG:
            raise ValueError(f"Unknown config key: '{key}'. Valid keys: {list(DEFAULT_CONFIG)}")
        coerced, ok = _coerce_key(key, value)
        if not ok:
            # Write boundary fails FAST (unlike load, which degrades): the caller
            # is program code passing a wrong type, not a hand-edited file.
            raise ValueError(
                f"Invalid type for '{key}': expected "
                f"{type(DEFAULT_CONFIG[key]).__name__}, got {type(value).__name__}"
            )
        _validate_allocation_numeric(key, coerced)
        cfg[key] = coerced
    _validate_allocation_relationships(cfg)
    return save_config(cfg)


def reset_config() -> dict[str, Any]:
    """Reset to factory defaults."""
    return save_config(DEFAULT_CONFIG)


# ─── Action Validation Gate ───────────────────────────────────────────────────


def validate_action(
    action: str,
    symbol: str,
    trade_usd: float,
    open_positions: int,
    current_cash: float | None = None,
    is_options: bool = False,
    current_price: float | None = None,
    *,
    require_live_permission: bool = True,
) -> ActionCheck:
    """Gate check before executing or recommending a trade.

    Financial limits (size, open positions, cash floor, scanner price) always
    run. Live-execution permission (``auto_trade``) is a separate last check
    so paper callers can skip only that permission without skipping caps.

    Returns ``ActionCheck`` (unpackable as ``ok, reason = ...``).
    """
    cfg = load_config()

    if not isinstance(action, str) or action not in TRADE_ACTIONS:
        return ActionCheck(
            False, "Invalid action — expected BUY, ADD, TRIM, or SELL", "INVALID_ACTION"
        )

    # Non-finite sizes fail closed: ``NaN > cap`` is False in IEEE-754, which
    # would otherwise let a missing/poisoned size through the dollar cap.
    if (
        not isinstance(trade_usd, (int, float))
        or isinstance(trade_usd, bool)
        or not math.isfinite(trade_usd)
    ):
        return ActionCheck(
            False, "Invalid trade size — expected a finite number", "INVALID_SIZE"
        )
    # Cash only feeds BUY/ADD gates. Rejecting it on SELL/TRIM would block
    # emergency exits when the broker snapshot is dirty.
    if (
        current_cash is not None
        and action in ("BUY", "ADD")
        and (
            not isinstance(current_cash, (int, float))
            or isinstance(current_cash, bool)
            or not math.isfinite(current_cash)
        )
    ):
        return ActionCheck(
            False, "Invalid cash — expected a finite number", "INVALID_CASH"
        )

    # Size / position / cash / price first — never gated on auto_trade.
    if is_options:
        cap = cfg["max_options_per_trade"]
        cap_label = "options"
    else:
        cap = cfg["max_stock_per_trade"]
        cap_label = "stock"

    if trade_usd > cap:
        return ActionCheck(
            False,
            (
                f"Trade size ${trade_usd:,.0f} exceeds max {cap_label} per trade "
                f"(${cap:,.0f}). Reduce position."
            ),
            "SIZE_CAP",
        )

    if action in ("BUY", "ADD") and open_positions >= cfg["max_open_positions"]:
        return ActionCheck(
            False,
            (
                f"Already at max open positions ({cfg['max_open_positions']}). "
                "Close a position before opening another."
            ),
            "POSITION_CAP",
        )

    if current_cash is not None and action in ("BUY", "ADD"):
        remaining = current_cash - trade_usd
        if remaining < cfg["min_cash_buffer"]:
            return ActionCheck(
                False,
                (
                    f"Trade would leave ${remaining:,.0f} cash — below "
                    f"${cfg['min_cash_buffer']:,.0f} minimum buffer. Reduce size."
                ),
                "CASH_FLOOR",
            )

    if current_price is not None and cfg["scanner_timeframe"] != "daily":
        if current_price < cfg["scanner_price_min"]:
            return ActionCheck(
                False,
                (
                    f"{symbol} price ${current_price:.2f} below scanner minimum "
                    f"${cfg['scanner_price_min']:.2f}"
                ),
                "PRICE_FILTER",
            )
        # Upper price ceiling is intended only for the penny-stock universe.
        # Enforce it for price-capped modes (mode-aware, not a hardcoded $50
        # magic number); a non-positive max disables the ceiling entirely.
        price_max = cfg.get("scanner_price_max") or 0
        if (
            price_max > 0
            and cfg["scanner_timeframe"] in PRICE_CAPPED_MODES
            and current_price > price_max
        ):
            return ActionCheck(
                False,
                (f"{symbol} price ${current_price:.2f} above scanner maximum ${price_max:.2f}"),
                "PRICE_FILTER",
            )

    if require_live_permission and not cfg["auto_trade"]:
        return ActionCheck(False, LIVE_PERMISSION_REASON, "LIVE_PERMISSION")

    return ActionCheck(True, "OK", "OK")


def get_allocation_summary(buying_power: float | None = None) -> dict:
    """
    Return a human-readable allocation summary for the report header.
    If buying_power is passed, calculates dollar amounts.
    """
    cfg = load_config()
    bp = buying_power or cfg.get("total_buying_power") or 0

    stock_alloc = bp * cfg["stock_allocation_pct"] / 100
    options_alloc = bp * cfg["options_allocation_pct"] / 100
    remaining = bp - stock_alloc - options_alloc

    return {
        "total_buying_power": bp,
        "stock_allocation_usd": round(stock_alloc, 2),
        "stock_allocation_pct": cfg["stock_allocation_pct"],
        "options_allocation_usd": round(options_alloc, 2),
        "options_allocation_pct": cfg["options_allocation_pct"],
        "remaining_usd": round(remaining, 2),
        "max_stock_per_trade": cfg["max_stock_per_trade"],
        "max_options_per_trade": cfg["max_options_per_trade"],
        "max_open_positions": cfg["max_open_positions"],
        "auto_trade": cfg["auto_trade"],
        "extended_hours": cfg["extended_hours"],
        "paper_mode": cfg["paper_mode"],
        "scanner_timeframe": cfg["scanner_timeframe"],
        "min_cash_buffer": cfg["min_cash_buffer"],
    }


# ─── Scanner timeframe helpers ────────────────────────────────────────────────

SCANNER_MODES = {
    "daily": {
        "period": "60d",
        "interval": "1d",
        "label": "Daily Scanner",
        "desc": "Key levels + sweep setups",
    },
    "1HR": {
        "period": "5d",
        "interval": "1h",
        "label": "1HR Scanner",
        "desc": "Multi-timeframe setups",
    },
    "5MIN": {
        "period": "1d",
        "interval": "5m",
        "label": "5MIN Scanner",
        "desc": "Intraday momentum setups",
    },
    "premarket": {
        "period": "1d",
        "interval": "5m",
        "label": "Premarket Scanner",
        "desc": "Unusual volume + big moves",
    },
    "stock": {
        "period": "30d",
        "interval": "1d",
        "label": "Stock Scanner",
        "desc": "Penny stocks $0.50–$10",
    },
    "forex-1HR": {
        "period": "5d",
        "interval": "1h",
        "label": "Forex 1HR Scan",
        "desc": "Majors, minors + metals",
    },
    "forex-4HR": {
        "period": "10d",
        "interval": "4h",
        "label": "Forex 4HR Scan",
        "desc": "Higher timeframe setups",
    },
    "forex-daily": {
        "period": "60d",
        "interval": "1d",
        "label": "Forex Daily Scan",
        "desc": "Daily trend setups",
    },
}


def get_scanner_params() -> dict:
    """Return the yfinance period/interval params for the active scanner timeframe."""
    cfg = load_config()
    mode = cfg.get("scanner_timeframe", "daily")
    return SCANNER_MODES.get(mode, SCANNER_MODES["daily"])


if __name__ == "__main__":
    cfg = load_config()
    print("Current config:")
    for k, v in cfg.items():
        print(f"  {k}: {v}")

    ok, reason = validate_action("BUY", "NVDA", trade_usd=3500, open_positions=2, current_cash=6000)
    print(f"\nValidation: {ok} — {reason}")
