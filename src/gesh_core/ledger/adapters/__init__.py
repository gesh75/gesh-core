"""Host-payload adapters for ledger recording (Phase 4B).

Each host pipeline gets its own adapter module. Adapters are the ONLY place
allowed to know host payload field names; the generic orchestration layer
(gesh_core.ledger.integration) stays host-agnostic.
"""

from gesh_core.ledger.adapters.daily_analysis import (
    DailyAnalysisRecording,
    SkippedDecision,
    record_daily_analysis_decision,
)

__all__ = [
    "DailyAnalysisRecording",
    "SkippedDecision",
    "record_daily_analysis_decision",
]
