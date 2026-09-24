"""Only exact ``BUY`` debits CASH_FLOOR. ADD/TRIM/EXECUTE with a target do not.

BUY-none and BUY-zero targets are already pinned. Managed adds/trims that
reuse ``target_position_pct`` currently leave cash unchanged — a later
``action != "SELL"`` rewrite would start debiting adds and starve paper.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import TradeIntent
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


@pytest.mark.parametrize("action", ["ADD", "TRIM", "EXECUTE"])
def test_non_buy_actions_do_not_debit_even_with_target(action: str) -> None:
    cfg = RiskConfig(paper_mode=False)
    intent = TradeIntent(
        symbol="NVDA",
        action=action,  # type: ignore[arg-type]
        confidence=1.0,
        source="m",
        target_position_pct=0.10,
    )
    portfolio = {"equity_summary": {"cash": 10_000.0, "portfolio_equity": 50_000.0}}
    assert _post_trade_cash_estimate(portfolio, intent, cfg) == 10_000.0


def test_buy_with_same_target_still_debits() -> None:
    cfg = RiskConfig(paper_mode=False)
    intent = TradeIntent(
        symbol="NVDA",
        action="BUY",
        confidence=1.0,
        source="m",
        target_position_pct=0.10,
    )
    portfolio = {"equity_summary": {"cash": 10_000.0, "portfolio_equity": 50_000.0}}
    assert _post_trade_cash_estimate(portfolio, intent, cfg) == 5_000.0
