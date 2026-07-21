"""Content-hash builders for ledger snapshots and analysis context.

context_hash identifies the decision input context. It does NOT identify one
execution run and does NOT imply that an LLM will produce the same output.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from gesh_core.ledger.canonical import content_hash
from gesh_core.ledger.versions import (
    CONTEXT_HASH_SCHEMA_VERSION,
    MARKET_QUOTE_SNAPSHOT_SCHEMA_VERSION,
    PORTFOLIO_SNAPSHOT_SCHEMA_VERSION,
    version_bundle,
)


def portfolio_snapshot_hash(
    *,
    tenant_id: str,
    holdings: Sequence[Mapping[str, Any]],
    cash: float | None,
    buying_power: float | None,
    total_equity: float | None,
    base_currency: str = "USD",
    risk_state: Mapping[str, Any] | None = None,
) -> str:
    """Hash of decision-relevant portfolio state.

    Includes: tenant_id, base_currency, holdings sorted by symbol
    (symbol, quantity, avg_cost), cash, buying_power, total_equity,
    optional risk_state, schema version.

    Excludes: captured_at, UI labels, secrets.
    """
    normalized_holdings: list[dict[str, Any]] = []
    for h in holdings:
        row: dict[str, Any] = {
            "symbol": str(h.get("symbol", "")).upper(),
            "quantity": h.get("quantity", h.get("qty", h.get("shares"))),
        }
        if h.get("avg_cost") is not None:
            row["avg_cost"] = h["avg_cost"]
        elif h.get("average_cost") is not None:
            row["avg_cost"] = h["average_cost"]
        normalized_holdings.append(row)
    normalized_holdings.sort(key=lambda r: r["symbol"])

    payload = {
        "schema_version": PORTFOLIO_SNAPSHOT_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "base_currency": base_currency,
        "total_equity": total_equity,
        "cash": cash,
        "buying_power": buying_power,
        "holdings": normalized_holdings,
        "risk_state": risk_state or None,
    }
    return content_hash(payload, prefix="ps")


def market_quote_snapshot_hash(
    *,
    tenant_id: str,
    symbol: str,
    asset_type: str = "equity",
    provider: str | None,
    as_of: str | None,
    available_time: str | None = None,
    retrieved_at: str | None = None,
    bid: float | None,
    ask: float | None,
    last: float | None,
    volume: float | None = None,
    quality_state: str,
) -> str:
    """Hash of the quote observation used for a decision.

    Includes: tenant_id, symbol, asset_type, provider, as_of, available_time,
    retrieved_at, bid/ask/last/volume, quality_state, schema version.
    """
    payload = {
        "schema_version": MARKET_QUOTE_SNAPSHOT_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "symbol": symbol.upper(),
        "asset_type": asset_type,
        "provider": provider,
        "as_of": as_of,
        "available_time": available_time,
        "retrieved_at": retrieved_at,
        "bid": bid,
        "ask": ask,
        "last": last,
        "volume": volume,
        "quality_state": quality_state,
    }
    return content_hash(payload, prefix="mqs")


def analysis_context_hash(
    *,
    tenant_id: str,
    source: str,
    portfolio_snapshot_hash_value: str,
    market_quote_snapshot_hashes: Sequence[str] | None = None,
    ai_provider: str | None = None,
    ai_model: str | None = None,
    prompt_bundle_hash: str | None = None,
    config_hash: str | None = None,
    extra_versions: Mapping[str, Any] | None = None,
) -> str:
    """Hash of the full decision input context (not one probabilistic run)."""
    versions = version_bundle()
    if extra_versions:
        versions = {**versions, **dict(extra_versions)}

    payload = {
        "schema_version": CONTEXT_HASH_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "source": source,
        "portfolio_snapshot_hash": portfolio_snapshot_hash_value,
        "market_quote_snapshot_hashes": list(market_quote_snapshot_hashes or []),
        "ai_provider": ai_provider,
        "ai_model": ai_model,
        "prompt_bundle_hash": prompt_bundle_hash,
        "config_hash": config_hash,
        "versions": versions,
    }
    return content_hash(payload, prefix="ctx")
