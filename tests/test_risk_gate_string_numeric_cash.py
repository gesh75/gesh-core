"""LIVE cash/equity sent as numeric strings must still debit.

Broker payloads sometimes serialize money as ``"10000.00"``. ``float()``
accepts that after ``or 0``. If this path started raising, the CASH_FLOOR
gate would fail open on a live BUY. Paper mode still ignores the live
strings and uses ``paper_cash_usd``.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def test_live_string_cash_and_equity_coerce_and_debit() -> None:
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    post = _post_trade_cash_estimate(
        {"equity_summary": {"cash": "10000.00", "portfolio_equity": "50000"}},
        intent,
        cfg,
    )
    assert post == pytest.approx(9_000.0)


def test_paper_mode_ignores_string_live_cash() -> None:
    cfg = RiskConfig(paper_mode=True, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    post = _post_trade_cash_estimate(
        {"equity_summary": {"cash": "300", "portfolio_equity": "50000"}},
        intent,
        cfg,
    )
    assert post == pytest.approx(99_000.0)
