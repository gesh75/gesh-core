"""GESH Decision Ledger foundation (Phase 4A) and recording orchestration (Phase 4B).

Provides version contracts, canonical serialization/hashing, additive snapshot
and recommendation tables, tenant-scoped repository helpers, and the generic
``record_analysis_decision`` orchestration with host adapters under
``gesh_core.ledger.adapters``.

No production analysis or trading path calls these helpers yet.
"""

from __future__ import annotations

from gesh_core.ledger.canonical import canonical_json, canonicalize, content_hash
from gesh_core.ledger.hashes import (
    analysis_context_hash,
    market_quote_snapshot_hash,
    portfolio_snapshot_hash,
)
from gesh_core.ledger.integration import (
    DecisionInput,
    LedgerConflictError,
    LedgerError,
    LedgerRecording,
    LedgerValidationError,
    LedgerWriteError,
    PortfolioInput,
    QuoteInput,
    record_analysis_decision,
)
from gesh_core.ledger.repository import (
    get_market_quote_snapshot,
    get_portfolio_snapshot,
    get_recommendation,
    insert_or_get_market_quote_snapshot,
    insert_or_get_portfolio_snapshot,
    insert_recommendation,
    list_recommendations,
)
from gesh_core.ledger.schema import init_ledger_tables
from gesh_core.ledger.versions import OWNER_TENANT_ID, version_bundle

__all__ = [
    "OWNER_TENANT_ID",
    "DecisionInput",
    "LedgerConflictError",
    "LedgerError",
    "LedgerRecording",
    "LedgerValidationError",
    "LedgerWriteError",
    "PortfolioInput",
    "QuoteInput",
    "analysis_context_hash",
    "canonical_json",
    "canonicalize",
    "content_hash",
    "get_market_quote_snapshot",
    "get_portfolio_snapshot",
    "get_recommendation",
    "init_ledger_tables",
    "insert_or_get_market_quote_snapshot",
    "insert_or_get_portfolio_snapshot",
    "insert_recommendation",
    "list_recommendations",
    "market_quote_snapshot_hash",
    "portfolio_snapshot_hash",
    "record_analysis_decision",
    "version_bundle",
]
