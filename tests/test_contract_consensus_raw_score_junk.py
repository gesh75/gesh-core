"""from_consensus treats raw_score as optional float and symbol as required.

Missing ``raw_score`` defaults to 0 — verdict still maps (conviction is the
P2 entry floor, not this adapter). A non-numeric raw_score currently raises
instead of degrading. A missing symbol is a KeyError, not a HOLD with an
empty ticker. Pin both so a later fail-closed change is reviewable and a
silent default-symbol would be caught.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.contract import from_consensus


def _row(**overrides):
    row = {
        "symbol": "NVDA",
        "verdict": "BUY",
        "confidence": 80,
        "active_nodes": 8,
        "total_nodes": 11,
    }
    row.update(overrides)
    return row


def test_missing_raw_score_defaults_to_zero_and_still_maps_verdict():
    intent = from_consensus(_row())
    assert intent.action == "BUY"
    assert intent.target_position_pct == pytest.approx(0.01)
    assert "raw_score=+0.00" in (intent.rationale or "")


def test_non_numeric_raw_score_currently_raises():
    with pytest.raises(ValueError):
        from_consensus(_row(raw_score="N/A"))


def test_none_raw_score_currently_raises():
    with pytest.raises(TypeError):
        from_consensus(_row(raw_score=None))


def test_missing_symbol_is_keyerror_not_empty_ticker():
    row = _row()
    del row["symbol"]
    with pytest.raises(KeyError):
        from_consensus(row)
