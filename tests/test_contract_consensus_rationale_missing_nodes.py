"""from_consensus rationale interpolates missing node counts as None, not 0.

A consensus row without active_nodes/total_nodes still builds an intent.
The rationale must keep the None placeholders so a host cannot later
treat "0/11" as a real participation reading.
"""

from __future__ import annotations

from gesh_core.trading.contract import from_consensus


def test_missing_node_counts_appear_as_none_in_rationale():
    intent = from_consensus(
        {
            "symbol": "NVDA",
            "verdict": "BUY",
            "raw_score": 0.6,
            "confidence": 80,
        }
    )
    assert intent.action == "BUY"
    assert "active_nodes=None/None" in (intent.rationale or "")
