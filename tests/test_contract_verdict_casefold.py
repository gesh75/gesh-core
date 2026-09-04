"""from_consensus uppercases the verdict before mapping.

Consensus rows have arrived as ``buy`` / ``strong sell`` from mixed hosts.
Without the .upper() the adapter would HOLD (unknown verdict) and drop a
real BUY/SELL. Pin the case-fold so a later rewrite cannot silently
downgrade actionable signals.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.contract import from_consensus


@pytest.mark.parametrize(
    ("verdict", "exp_action", "exp_target"),
    [
        ("buy", "BUY", 0.01),
        ("strong buy", "BUY", 0.02),
        ("sell", "SELL", 0.0),
        ("Strong Sell", "SELL", 0.0),
        ("hold", "HOLD", None),
        ("insufficient data", "HOLD", None),
    ],
)
def test_from_consensus_maps_mixed_case_verdicts(
    verdict: str, exp_action: str, exp_target: float | None
) -> None:
    intent = from_consensus(
        {
            "symbol": "NVDA",
            "verdict": verdict,
            "raw_score": 0.6,
            "confidence": 80,
            "active_nodes": 8,
            "total_nodes": 11,
        },
        max_position_pct=0.02,
    )
    assert intent.action == exp_action
    assert intent.target_position_pct == exp_target
    assert intent.source == "consensus"
