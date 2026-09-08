"""from_consensus scales STRONG BUY at 1.0×cap and BUY at 0.5×cap.

Main tests only pin the 2% default. A host that passes a different
max_position_pct (or 0.0) must keep the 1.0 / 0.5 ratio, and SELL must
still close to 0 rather than inherit the cap.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.contract import from_consensus


def _row(verdict: str) -> dict:
    return {
        "symbol": "NVDA",
        "verdict": verdict,
        "raw_score": 0.6,
        "confidence": 80,
        "active_nodes": 8,
        "total_nodes": 11,
    }


@pytest.mark.parametrize("cap", [0.04, 0.10, 0.25])
def test_strong_buy_uses_full_custom_cap(cap):
    intent = from_consensus(_row("STRONG BUY"), max_position_pct=cap)
    assert intent.action == "BUY"
    assert intent.target_position_pct == pytest.approx(cap)


@pytest.mark.parametrize("cap", [0.04, 0.10, 0.25])
def test_buy_uses_half_custom_cap(cap):
    intent = from_consensus(_row("BUY"), max_position_pct=cap)
    assert intent.action == "BUY"
    assert intent.target_position_pct == pytest.approx(round(cap * 0.5, 6))


def test_sell_target_is_zero_regardless_of_cap():
    intent = from_consensus(_row("STRONG SELL"), max_position_pct=0.25)
    assert intent.action == "SELL"
    assert intent.target_position_pct == 0.0
