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
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
    "total_buying_power":       None,      # set at runtime from Robinhood profile
    "stock_allocation_pct":     70.0,      # % of buying power for stocks
    "options_allocation_pct":   30.0,      # % of buying power for options

    # Per-trade hard caps
    "max_stock_per_trade":      5000.0,    # max $ on a single stock trade
    "max_options_per_trade":    2000.0,    # max $ on a single options trade
    "max_open_positions":       5,         # max simultaneous open positions
    "max_open_contracts":       3,         # max simultaneous open options contracts
    "min_cash_buffer":          500.0,     # never deploy below this cash level

    # Scanner filters
    "scanner_price_min":        0.10,      # min stock price for scanner
    "scanner_price_max":        10.00,     # max price ceiling — enforced ONLY in PRICE_CAPPED_MODES (penny universe)
    "scanner_volume_min":       200_000,   # min daily volume
    "scanner_timeframe":        "daily",   # daily | 1HR | 5MIN | premarket | forex-1HR | forex-4HR

    # Execution gates
    "auto_trade":               False,     # True = live execution enabled
    "extended_hours":           True,      # pre-market & after-hours
    "paper_mode":               False,     # True = all actions route to paper_trades

    # Portfolio screener universe
    "screener_universe":        "default", # default | aggressive | conservative | forex

    # Metadata
    "last_updated":             None,
    "version":                  "1.1",
}

# Scanner modes where the scanner_price_max ceiling is meaningful (penny-stock
# universe). Intraday/forex modes intentionally have NO upper price cap.
PRICE_CAPPED_MODES = {"stock"}

# Canonical actions accepted by the execution gate. Rejecting rather than
# normalizing malformed actions keeps every safety check fail-closed.
TRADE_ACTIONS = frozenset({"BUY", "ADD", "TRIM", "SELL"})

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
        return value, True                      # runtime-set keys (buying power, timestamp)
    if isinstance(default, bool):
        return (value, True) if isinstance(value, bool) else (default, False)
    if isinstance(default, (int, float)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return default, False
        return (float(value) if isinstance(default, float) else value), True
    if isinstance(default, str):
        return (value, True) if isinstance(value, str) else (default, False)
    return value, True


def load_config() -> dict[str, Any]:
    """Load config from disk, merging with defaults for any missing keys.

    Boundary-validated: every known key is type-checked against DEFAULT_CONFIG
    and falls back per-key (with a warning) on mismatch — a hand-edited value
    must not crash or silently weaken the execution gates. Unknown keys pass
    through untouched for forward compatibility. A corrupt/unreadable file
    degrades to the defaults instead of raising; the corrupt file is left on
    disk for inspection and the next save repairs it.
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
    for key, value in (stored.items() if isinstance(stored, dict) else ()):
        if key in DEFAULT_CONFIG:
            coerced, ok = _coerce_key(key, value)
            if not ok:
                logger.warning(
                    "gesh_config.json: %r has invalid type %s (%r) — using default %r",
                    key, type(value).__name__, value, DEFAULT_CONFIG[key],
                )
            cfg[key] = coerced
        else:
            cfg[key] = value                    # forward-compat passthrough
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
        cfg[key] = coerced
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
) -> tuple[bool, str]:
    """
    Gate check before executing or recommending a trade.
    Returns (allowed: bool, reason: str).

    Checks applied:
      1. Auto-trade gate (if auto_trade=False, always block live execution)
      2. Max $ per trade (BUY/ADD only — exits must not be trapped by the entry cap)
      3. Max open positions (BUY/ADD only)
      4. Cash buffer floor (BUY/ADD only)
      5. Scanner price filter (BUY/ADD only, if price provided)
    """
    cfg = load_config()

    if not isinstance(action, str) or action not in TRADE_ACTIONS:
        return False, "Invalid action — expected BUY, ADD, TRIM, or SELL"

    # 1. Auto-trade gate
    if not cfg["auto_trade"]:
        return False, "Auto-trade is OFF — review and execute manually"

    opening = action in ("BUY", "ADD")

    # 2. Max $ per trade — entry sizing only. A position that appreciated past
    #    max_stock_per_trade (or a loser that the scanner band no longer admits)
    #    must still be closeable; "Reduce position" is meaningless on a SELL.
    if opening:
        if is_options:
            cap = cfg["max_options_per_trade"]
            cap_label = "options"
        else:
            cap = cfg["max_stock_per_trade"]
            cap_label = "stock"

        if trade_usd > cap:
            return False, (
                f"Trade size ${trade_usd:,.0f} exceeds max {cap_label} per trade "
                f"(${cap:,.0f}). Reduce position."
            )

    # 3. Max open positions
    if opening and open_positions >= cfg["max_open_positions"]:
        return False, (
            f"Already at max open positions ({cfg['max_open_positions']}). "
            "Close a position before opening another."
        )

    # 4. Cash buffer
    if opening and current_cash is not None:
        remaining = current_cash - trade_usd
        if remaining < cfg["min_cash_buffer"]:
            return False, (
                f"Trade would leave ${remaining:,.0f} cash — below "
                f"${cfg['min_cash_buffer']:,.0f} minimum buffer. Reduce size."
            )

    # 5. Price filter (scanner mode) — entry universe only. A name that
    #    broke out above the ceiling or collapsed below the floor would
    #    otherwise be un-sellable through this gate.
    if opening and current_price is not None and cfg["scanner_timeframe"] != "daily":
        if current_price < cfg["scanner_price_min"]:
            return False, (
                f"{symbol} price ${current_price:.2f} below scanner minimum "
                f"${cfg['scanner_price_min']:.2f}"
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
            return False, (
                f"{symbol} price ${current_price:.2f} above scanner maximum "
                f"${price_max:.2f}"
            )

    return True, "OK"


def get_allocation_summary(buying_power: float | None = None) -> dict:
    """
    Return a human-readable allocation summary for the report header.
    If buying_power is passed, calculates dollar amounts.
    """
    cfg = load_config()
    bp = buying_power or cfg.get("total_buying_power") or 0

    stock_alloc   = bp * cfg["stock_allocation_pct"]   / 100
    options_alloc = bp * cfg["options_allocation_pct"] / 100
    remaining     = bp - stock_alloc - options_alloc

    return {
        "total_buying_power":    bp,
        "stock_allocation_usd":  round(stock_alloc, 2),
        "stock_allocation_pct":  cfg["stock_allocation_pct"],
        "options_allocation_usd": round(options_alloc, 2),
        "options_allocation_pct": cfg["options_allocation_pct"],
        "remaining_usd":         round(remaining, 2),
        "max_stock_per_trade":   cfg["max_stock_per_trade"],
        "max_options_per_trade": cfg["max_options_per_trade"],
        "max_open_positions":    cfg["max_open_positions"],
        "auto_trade":            cfg["auto_trade"],
        "extended_hours":        cfg["extended_hours"],
        "paper_mode":            cfg["paper_mode"],
        "scanner_timeframe":     cfg["scanner_timeframe"],
        "min_cash_buffer":       cfg["min_cash_buffer"],
    }


# ─── Scanner timeframe helpers ────────────────────────────────────────────────

SCANNER_MODES = {
    "daily":     {"period": "60d",  "interval": "1d",  "label": "Daily Scanner",     "desc": "Key levels + sweep setups"},
    "1HR":       {"period": "5d",   "interval": "1h",  "label": "1HR Scanner",       "desc": "Multi-timeframe setups"},
    "5MIN":      {"period": "1d",   "interval": "5m",  "label": "5MIN Scanner",      "desc": "Intraday momentum setups"},
    "premarket": {"period": "1d",   "interval": "5m",  "label": "Premarket Scanner", "desc": "Unusual volume + big moves"},
    "stock":     {"period": "30d",  "interval": "1d",  "label": "Stock Scanner",     "desc": "Penny stocks $0.50–$10"},
    "forex-1HR": {"period": "5d",   "interval": "1h",  "label": "Forex 1HR Scan",    "desc": "Majors, minors + metals"},
    "forex-4HR": {"period": "10d",  "interval": "4h",  "label": "Forex 4HR Scan",    "desc": "Higher timeframe setups"},
    "forex-daily":{"period": "60d", "interval": "1d",  "label": "Forex Daily Scan",  "desc": "Daily trend setups"},
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
