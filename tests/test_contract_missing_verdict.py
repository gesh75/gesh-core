"""from_consensus must fail closed to HOLD when the verdict is missing or blank
— never invent a BUY/SELL. Empty symbols must fail validate() so a broker
cannot be asked to trade ''.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.contract import TradeIntent, from_consensus


def _row(**overrides):
    row = {
        "symbol": "NVDA",
        "raw_score": 0.90,
        "confidence": 90,
        "active_nodes": 9,
        "total_nodes": 11,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize("overrides", [{}, {"verdict": None}, {"verdict": ""}, {"verdict": "   "}])
def test_from_consensus_missing_or_blank_verdict_is_hold(overrides):
    intent = from_consensus(_row(**overrides))
    assert intent.action == "HOLD"
    assert intent.target_position_pct is None
    assert intent.source == "consensus"
    assert intent.validate() == []


def test_validate_empty_symbol_is_rejected():
    problems = TradeIntent(symbol="", action="HOLD", confidence=1.0, source="m").validate()
    assert any("symbol invalid" in p for p in problems)
