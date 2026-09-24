"""Present-but-None Momentum/Trend is a failed price confirm, not an absent node.

``"Momentum" in votes`` is True for a None value, so both nodes abstaining
blocks the BUY. Missing both keys fail-open (already pinned). Confusing the
two would let a scan row with explicit null price nodes through.
"""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_both_price_nodes_none_blocks() -> None:
    row = {
        "verdict": "BUY",
        "votes": {
            "Momentum": None,
            "Trend": None,
            "Rel.Strength": 1,
            "Volume": 1,
            "Macro": 1,
        },
        "bullish": 4,
        "bearish": 0,
    }
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "price confirm" in d.reason.lower() or "Momentum" in d.reason
