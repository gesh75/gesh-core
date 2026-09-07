"""Padded consensus verdicts currently fall through to HOLD.

``from_consensus`` uppercases ``verdict`` but never strips it. A CSV/API export
with a leading space or trailing newline therefore misses every STRONG BUY/BUY
branch and emits a valid HOLD — no crash, no gate rejection, just a missed
entry. Pin the current mapping so a later strip is reviewable and cannot
silently start treating padded SELL as an exit.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.contract import from_consensus


def _row(verdict: str) -> dict:
    return {
        "symbol": "NVDA",
        "verdict": verdict,
        "raw_score": 0.60,
        "confidence": 80,
        "active_nodes": 8,
        "total_nodes": 11,
    }


@pytest.mark.parametrize("verdict", [" STRONG BUY", "BUY\n", "SELL ", "\tHOLD"])
def test_padded_verdict_currently_maps_to_hold(verdict: str) -> None:
    intent = from_consensus(_row(verdict), max_position_pct=0.02)
    assert intent.action == "HOLD"
    assert intent.target_position_pct is None
    assert intent.validate() == []


def test_unpadded_strong_buy_still_scales_to_cap() -> None:
    intent = from_consensus(_row("STRONG BUY"), max_position_pct=0.02)
    assert intent.action == "BUY"
    assert intent.target_position_pct == pytest.approx(0.02)
