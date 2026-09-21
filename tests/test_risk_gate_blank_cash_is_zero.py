"""Blank LIVE cash/equity must coerce to $0, not raise.

Broker payloads sometimes send ``""`` or JSON null for cash. ``or 0`` keeps
the CASH_FLOOR math running. A TypeError here would skip the gate entirely
and fail-open a live BUY.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def test_empty_string_cash_and_equity_are_zero() -> None:
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    post = _post_trade_cash_estimate(
        {"equity_summary": {"cash": "", "portfolio_equity": ""}},
        intent,
        cfg,
    )
    assert post == pytest.approx(0.0)


def test_none_cash_with_equity_still_debits() -> None:
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    post = _post_trade_cash_estimate(
        {"equity_summary": {"cash": None, "portfolio_equity": 50_000.0}},
        intent,
        cfg,
    )
    assert post == pytest.approx(-1_000.0)
