"""Zero ``max_position_pct`` still emits gate-valid BUY/SELL intents.

All BUY targets scale from the adapter cap. Cap ``0`` yields
``target_position_pct=0.0``, and ``validate()`` only rejects a *missing*
target — not a zero-weight BUY. A misconfigured ``MAX_POSITION_PCT=0``
therefore consumes gate/audit capacity while sizing to a no-op. Pin that
so a later reject-zero change is reviewable.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import from_consensus
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def _row(verdict: str) -> dict:
    return {
        "symbol": "NVDA",
        "verdict": verdict,
        "raw_score": 0.60,
        "confidence": 80,
        "active_nodes": 8,
        "total_nodes": 11,
    }


@pytest.mark.parametrize("verdict,exp_action", [("STRONG BUY", "BUY"), ("BUY", "BUY")])
def test_zero_cap_buy_is_valid_zero_weight(verdict: str, exp_action: str) -> None:
    intent = from_consensus(_row(verdict), max_position_pct=0.0)
    assert intent.action == exp_action
    assert intent.target_position_pct == 0.0
    assert intent.validate() == []


def test_zero_cap_sell_still_closes() -> None:
    intent = from_consensus(_row("SELL"), max_position_pct=0.0)
    assert intent.action == "SELL"
    assert intent.target_position_pct == 0.0
    assert intent.validate() == []


def test_zero_weight_buy_does_not_debit_cash() -> None:
    intent = from_consensus(_row("STRONG BUY"), max_position_pct=0.0)
    cfg = RiskConfig(paper_mode=False)
    post = _post_trade_cash_estimate(
        {"equity_summary": {"cash": 10_000.0, "portfolio_equity": 50_000.0}},
        intent,
        cfg,
    )
    # ``target_position_pct`` is falsy, so CASH_FLOOR treats this as a no-debit.
    assert post == pytest.approx(10_000.0)
