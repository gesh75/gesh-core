"""Version contracts for the GESH Decision Ledger (Phase 4A).

These constants are the single source of truth for schema and engine versions
that participate in context hashing. Changing any value intentionally changes
the corresponding hash inputs.

Initial values reflect the current (pre-ledger) production codebase.
"""

from __future__ import annotations

from typing import Any

# Schema versions (integers). Bump when table shape or hash field set changes.
LEDGER_SCHEMA_VERSION = 1
PORTFOLIO_SNAPSHOT_SCHEMA_VERSION = 1
MARKET_QUOTE_SNAPSHOT_SCHEMA_VERSION = 1
RECOMMENDATION_SCHEMA_VERSION = 1
CONTEXT_HASH_SCHEMA_VERSION = 1
# Versions the recommendation-ID identity payload (tenant_id, symbol,
# decision_type, context_hash). Deliberately NOT part of version_bundle():
# it versions the ID scheme, not the decision context, so bumping it must not
# perturb context hashes.
RECOMMENDATION_ID_SCHEMA_VERSION = 1

# Engine / model versions (semver strings).
CONSENSUS_ENGINE_VERSION = "1.0.0"
QUANT_ENGINE_VERSION = "1.0.0"
KELLY_ENGINE_VERSION = "1.0.0"
MONTE_CARLO_ENGINE_VERSION = "1.0.0"
RISK_GATE_VERSION = "1.0.0"
PROMPT_BUNDLE_VERSION = "1.0.0"
EXECUTION_MODEL_VERSION = "legacy"
DATA_QUALITY_MODEL_VERSION = "1.0.0"

# Explicit owner/system tenant identity for non-customer (daily-chain) rows.
# Never use NULL for tenant ownership.
OWNER_TENANT_ID = "owner"


def version_bundle() -> dict[str, Any]:
    """Return the full version bundle with stable key order for hashing."""
    return {
        "ledger_schema": LEDGER_SCHEMA_VERSION,
        "portfolio_snapshot_schema": PORTFOLIO_SNAPSHOT_SCHEMA_VERSION,
        "market_quote_snapshot_schema": MARKET_QUOTE_SNAPSHOT_SCHEMA_VERSION,
        "recommendation_schema": RECOMMENDATION_SCHEMA_VERSION,
        "context_hash_schema": CONTEXT_HASH_SCHEMA_VERSION,
        "consensus_engine": CONSENSUS_ENGINE_VERSION,
        "quant_engine": QUANT_ENGINE_VERSION,
        "kelly_engine": KELLY_ENGINE_VERSION,
        "monte_carlo_engine": MONTE_CARLO_ENGINE_VERSION,
        "risk_gate": RISK_GATE_VERSION,
        "prompt_bundle": PROMPT_BUNDLE_VERSION,
        "execution_model": EXECUTION_MODEL_VERSION,
        "data_quality_model": DATA_QUALITY_MODEL_VERSION,
    }
