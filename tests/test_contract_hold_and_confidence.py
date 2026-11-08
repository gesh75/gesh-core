"""HOLD must stay gate-valid without a target; missing consensus confidence is 0.

BUY/SELL without ``target_position_pct`` are rejected (stop-sweep depends on
that). HOLD is a no-op and must not pick up the same requirement. Confidence
is data-coverage only — a missing field must not crash the adapter or invent
conviction.
"""
from __future__ import annotations

from gesh_core.trading.contract import TradeIntent, from_consensus


def test_validate_hold_does_not_require_target_position_pct():
    problems = TradeIntent(
        symbol="NVDA", action="HOLD", confidence=1.0, source="consensus"
    ).validate()
    assert problems == []


def test_from_consensus_missing_confidence_is_zero_not_conviction():
    intent = from_consensus(
        {
            "symbol": "NVDA",
            "verdict": "HOLD",
            "raw_score": 0.60,
            "active_nodes": 8,
            "total_nodes": 11,
        }
    )
    assert intent.action == "HOLD"
    assert intent.target_position_pct is None
    assert intent.confidence == 0.0
    assert intent.validate() == []
