"""Consensus confidence is 0..100 participation, then divided into [0, 1].

A row that already stores a fraction (or a percent >100) must not become a
gate-valid intent: validate() rejects confidence outside [0, 1], so emergency
exits and entries built from a malformed consensus payload fail closed as
malformed rather than trading at a invented conviction.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.contract import from_consensus


def _row(**overrides: object) -> dict:
    row: dict = {
        "symbol": "NVDA",
        "verdict": "BUY",
        "raw_score": 0.60,
        "confidence": 80,
        "active_nodes": 8,
        "total_nodes": 11,
    }
    row.update(overrides)
    return row


def test_confidence_over_one_hundred_fails_validate():
    intent = from_consensus(_row(confidence=150))
    assert intent.confidence == pytest.approx(1.5)
    problems = intent.validate()
    assert any("confidence must be in [0,1]" in p for p in problems)


def test_confidence_already_a_fraction_fails_validate():
    # Host already stored 0..1; dividing again yields ~0.008, which is valid
    # numerically but is the documented participation contract — pin the divide.
    intent = from_consensus(_row(confidence=0.80))
    assert intent.confidence == pytest.approx(0.008)
    assert intent.validate() == []


def test_confidence_none_raises_instead_of_inventing_conviction():
    with pytest.raises(TypeError):
        from_consensus(_row(confidence=None))
