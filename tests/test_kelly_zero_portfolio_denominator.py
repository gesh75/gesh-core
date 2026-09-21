"""Zero / negative portfolio denominator in kelly_size_holding.

``current_pct = current_equity / total_portfolio`` is guarded with
``if total_portfolio > 0 else 0``. A zero or negative book must not
divide-by-zero or leak inf into the action classifier / JSON payload —
that path is what the /kelly dashboard and consensus size against.
"""
from __future__ import annotations

import numpy as np
import pytest

from gesh_core.kelly import kelly_size_holding

# Deterministic upward drift so sizing produces a positive final_pct.
_RETURNS = np.full(80, 0.002, dtype=float) + np.linspace(-0.001, 0.001, 80)


def test_zero_portfolio_sets_current_pct_zero_and_recommends_zero_usd() -> None:
    res = kelly_size_holding(
        "NVDA",
        current_equity=1_000.0,
        total_portfolio=0.0,
        avg_cost=10.0,
        current_price=12.0,
        returns=_RETURNS,
    )
    assert "error" not in res
    assert res["current_pct"] == 0.0
    assert res["recommended_usd"] == 0.0
    assert res["delta_usd"] == pytest.approx(-1_000.0)
    # 0 current vs a positive target is an ADD, not a crash / AVOID.
    assert res["action"] == "ADD"
    assert res["optimal_pct"] > 0


def test_negative_portfolio_does_not_divide() -> None:
    res = kelly_size_holding(
        "NVDA",
        current_equity=1_000.0,
        total_portfolio=-5_000.0,
        avg_cost=10.0,
        current_price=12.0,
        returns=_RETURNS,
    )
    assert "error" not in res
    assert res["current_pct"] == 0.0
    # recommended_usd = final_pct * total_portfolio — negative book stays negative.
    assert res["recommended_usd"] < 0
    assert np.isfinite(res["current_pct"])
    assert np.isfinite(res["delta_pct"])
