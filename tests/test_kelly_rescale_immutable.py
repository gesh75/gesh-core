"""_rescale_result returns a new dict and reclassifies action from scaled weight.

The reconciliation overlay must not mutate the per-name Kelly row (dashboard
and audit both keep the pre-haircut number). Action/color must follow the
scaled optimal_pct, not the pre-overlay band.
"""

from __future__ import annotations

import pytest

from gesh_core.kelly import _rescale_result


def test_rescale_does_not_mutate_input_and_recomputes_action():
    original = {
        "symbol": "NVDA",
        "optimal_pct": 20.0,
        "current_pct": 8.0,
        "half_kelly": 20.0,
        "recommended_usd": 20_000.0,
        "delta_usd": 12_000.0,
        "delta_pct": 12.0,
        "action": "ADD",
        "action_color": "green",
    }
    snapshot = dict(original)

    out = _rescale_result(
        original,
        equity=8_000.0,
        total_portfolio=100_000.0,
        corr_haircut=0.5,
        gross_factor=1.0,
    )

    assert original == snapshot
    assert out is not original
    # 20.0 * 0.5 * 1.0 → 10.0%. current 8% is inside the 0.6..1.3 HOLD band.
    assert out["optimal_pct"] == pytest.approx(10.0)
    assert out["half_kelly"] == pytest.approx(10.0)
    assert out["recommended_usd"] == pytest.approx(10_000.0)
    assert out["delta_usd"] == pytest.approx(2_000.0)
    assert out["corr_haircut"] == pytest.approx(0.5)
    assert out["action"] == "HOLD"
    assert out["action_color"] == "cyan"
