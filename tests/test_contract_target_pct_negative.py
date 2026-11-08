"""target_position_pct bounds: negative is rejected; 0.0 BUY is still valid.

Existing tests pin the 1.5 overflow. The negative side is the typo / inverted
size path. BUY at 0.0 is in [0, 1] and is not None, so validate() accepts a
zero-size entry — CASH_FLOOR then skips the debit (truthy-target check).
"""
from __future__ import annotations

from gesh_core.trading.contract import TradeIntent, manual


def test_validate_rejects_negative_target_position_pct():
    problems = manual("NVDA", "BUY", target_position_pct=-0.01).validate()
    assert any("target_position_pct must be in [0,1]" in p for p in problems)


def test_buy_with_zero_target_is_structurally_valid():
    intent = manual("NVDA", "BUY", target_position_pct=0.0)
    assert intent.validate() == []
    assert intent.target_position_pct == 0.0


def test_sell_with_zero_target_is_structurally_valid():
    # stop_sweep and full-close SELLs rely on 0.0 being valid, not None.
    intent = TradeIntent(
        symbol="NVDA", action="SELL", confidence=1.0, source="stop_sweep",
        target_position_pct=0.0,
    )
    assert intent.validate() == []
