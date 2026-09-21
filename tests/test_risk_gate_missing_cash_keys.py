"""CASH_FLOOR leftover: LIVE cash is ``float(summary.get("cash", 0) or 0)``.

Missing keys must not crash the gate (empty summary → $0). A junk string
currently raises ValueError — pin that so a fail-closed change is deliberate.
Paper mode still ignores the live cash field entirely.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def test_live_missing_equity_summary_uses_zero_cash() -> None:
    cfg = RiskConfig(paper_mode=False, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    post = _post_trade_cash_estimate({}, intent, cfg)
    assert post == pytest.approx(0.0)


def test_live_missing_cash_key_uses_zero() -> None:
    cfg = RiskConfig(paper_mode=False, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.10)
    portfolio = {"equity_summary": {"portfolio_equity": 50_000.0}}
    post = _post_trade_cash_estimate(portfolio, intent, cfg)
    # 0 - 0.10 * 50_000
    assert post == pytest.approx(-5_000.0)


def test_live_junk_cash_currently_raises() -> None:
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    portfolio = {"equity_summary": {"cash": "N/A", "portfolio_equity": 50_000.0}}
    with pytest.raises(ValueError):
        _post_trade_cash_estimate(portfolio, intent, cfg)


def test_paper_ignores_junk_live_cash() -> None:
    cfg = RiskConfig(paper_mode=True, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    portfolio = {"equity_summary": {"cash": "N/A", "portfolio_equity": 50_000.0}}
    post = _post_trade_cash_estimate(portfolio, intent, cfg)
    assert post == pytest.approx(99_000.0)
