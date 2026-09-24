"""NaN raw_score must not crash from_consensus or change participation confidence.

Conviction is gated later by ``entry_floor_blocks``. The adapter still emits a
BUY with confidence = coverage/100. Pin that a missing consensus number does
not raise inside the rationale f-string and does not get blended into
confidence.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.contract import from_consensus


def test_nan_raw_score_still_maps_buy_and_keeps_coverage_confidence() -> None:
    intent = from_consensus(
        {
            "symbol": "NVDA",
            "verdict": "BUY",
            "raw_score": float("nan"),
            "confidence": 80,
            "active_nodes": 8,
            "total_nodes": 11,
        },
        max_position_pct=0.02,
    )
    assert intent.action == "BUY"
    assert intent.target_position_pct == pytest.approx(0.01)
    assert intent.confidence == pytest.approx(0.80)
    assert intent.source == "consensus"
    assert "nan" in (intent.rationale or "").lower()
