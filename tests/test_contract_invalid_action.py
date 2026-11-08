"""TradeIntent.validate must reject non-canonical actions at runtime.

Action is a Literal in the type system, but callers construct intents from
engine/JSON payloads. TRIM/ADD/lowercase/empty must fail closed rather than
reaching the risk gate as an unrecognized verb.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.contract import TradeIntent


@pytest.mark.parametrize("action", ["TRIM", "ADD", "EXECUTE", "buy", "sell", ""])
def test_validate_rejects_noncanonical_action(action: str):
    problems = TradeIntent(
        symbol="NVDA",
        action=action,  # type: ignore[arg-type]
        confidence=1.0,
        source="manual",
        target_position_pct=0.02,
    ).validate()
    assert any("action must be BUY/SELL/HOLD" in p for p in problems)
