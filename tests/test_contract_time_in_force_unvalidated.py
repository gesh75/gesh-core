"""``TradeIntent.validate()`` currently ignores ``time_in_force``.

Only action, confidence, target, stops, and symbol are checked. Wrong-case,
unknown, or empty TIF values therefore pass the contract and can reach the
broker layer undetected. Pin the current hole so a later enum check cannot
silently start rejecting historical JSON that used ``DAY``.
"""
from __future__ import annotations

from gesh_core.trading.contract import TradeIntent, manual


@pytest.mark.parametrize("tif", ["DAY", "week", "", "gtc "])
def test_invalid_time_in_force_currently_passes_validate(tif: str) -> None:
    intent = TradeIntent(
        symbol="NVDA",
        action="BUY",
        confidence=1.0,
        source="manual",
        target_position_pct=0.02,
        time_in_force=tif,  # type: ignore[arg-type]
    )
    assert intent.validate() == []


def test_manual_default_time_in_force_is_day() -> None:
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    assert intent.time_in_force == "day"
    assert intent.validate() == []
