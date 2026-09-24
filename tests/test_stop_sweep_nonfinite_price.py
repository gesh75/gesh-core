"""A NaN/inf breach price must still emit a gate-valid full-close SELL.

``stop_sweep_intent`` formats price/stop into the rationale (``:.2f`` does not
raise on NaN/inf) and never copies them onto ``stop_loss``. The product bug
this helper exists to prevent is a missing ``target_position_pct`` — a
poisoned quote must not recreate that reject.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.autopilot_core import stop_sweep_intent


@pytest.mark.parametrize("price", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_price_is_still_gate_valid_full_close(price: float) -> None:
    intent = stop_sweep_intent("hood", price=price, stop=11.0, book="paper")
    assert intent.validate() == []
    assert intent.action == "SELL"
    assert intent.target_position_pct == 0.0
    assert intent.source == "stop_sweep"
    assert intent.symbol == "HOOD"
    assert "paper" in (intent.rationale or "")
