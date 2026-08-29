"""Kelly AI-valuation penalty tiers and empty-book current_pct guard.

Only the AVOID/SELL 0.5× haircut is pinned on main. REDUCE and the pct_diff
bands shrink live size; a regression here over-allocates into names the AI
already called overvalued. total_portfolio=0 is the empty-dashboard path.
"""

from __future__ import annotations

import numpy as np

from gesh_core.kelly import kelly_size_holding

_POSITIVE_DRIFT = np.random.default_rng(42).normal(0.002, 0.01, 120).astype(float)


def _size(**kwargs: object) -> dict:
    return kelly_size_holding(
        "X",
        1_000,
        100_000,
        10,
        12,
        returns=_POSITIVE_DRIFT,
        **kwargs,
    )


def test_ai_penalty_tiers_and_verdict_precedence():
    base = _size()
    avoid = _size(ai_eval={"verdict": "AVOID"})
    sell = _size(ai_eval={"verdict": "SELL", "pct_diff": -1})
    reduce = _size(ai_eval={"verdict": "REDUCE"})
    severe = _size(ai_eval={"verdict": "BUY", "pct_diff": -20})
    slight = _size(ai_eval={"verdict": "BUY", "pct_diff": -10})
    none = _size(ai_eval={"verdict": "BUY", "pct_diff": 5})

    assert avoid["ai_penalty"] == 0.5
    assert sell["ai_penalty"] == 0.5  # verdict beats a mild pct_diff
    assert reduce["ai_penalty"] == 0.8
    assert severe["ai_penalty"] == 0.6
    assert slight["ai_penalty"] == 0.8
    assert none["ai_penalty"] == 1.0

    assert avoid["optimal_pct"] <= reduce["optimal_pct"] <= base["optimal_pct"]
    assert severe["optimal_pct"] <= slight["optimal_pct"] <= none["optimal_pct"]


def test_zero_total_portfolio_does_not_divide_and_reports_zero_current_pct():
    out = kelly_size_holding(
        "X",
        5_000,
        0,
        10,
        12,
        returns=_POSITIVE_DRIFT,
    )
    assert "error" not in out
    assert out["current_pct"] == 0.0
    assert out["recommended_usd"] == 0.0
