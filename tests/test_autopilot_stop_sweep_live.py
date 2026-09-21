"""stop_sweep_intent is gate-valid for the live book and uppercases the ticker.

The product once shipped a SELL without target_position_pct=0.0 and every
emergency exit was rejected as malformed. Paper is pinned on main; live
must stay equally valid, and a lowercase ticker from the close-scan must
not produce a symbol that fails TradeIntent.validate().
"""
from __future__ import annotations

from gesh_core.trading.autopilot_core import stop_sweep_intent


def test_live_book_is_gate_valid_full_close() -> None:
    intent = stop_sweep_intent("hood", price=12.5, stop=11.0, book="live")
    assert intent.validate() == []
    assert intent.action == "SELL"
    assert intent.target_position_pct == 0.0
    assert intent.source == "stop_sweep"
    assert intent.symbol == "HOOD"
    assert intent.confidence == 1.0
    assert "live" in (intent.rationale or "")
    assert "12.50" in (intent.rationale or "")
    assert "11.00" in (intent.rationale or "")
