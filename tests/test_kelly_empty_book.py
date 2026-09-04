"""run_kelly_analysis on an empty holdings list must not leak NaN.

An all-error book already reports portfolio_kelly_score 0.0 (np.mean([]) is
NaN). The empty-holdings path is the other way to get an empty sized list —
a dashboard refresh against a flat account must stay JSON-safe.
"""
from __future__ import annotations

import numpy as np

from gesh_core.kelly import run_kelly_analysis


def test_empty_holdings_score_is_zero_and_unscaled() -> None:
    out = run_kelly_analysis([], total_portfolio=100_000.0)
    assert out["holdings"] == []
    assert out["trim_list"] == []
    assert out["add_list"] == []
    assert out["avoid_list"] == []
    assert out["total_optimal_allocated_pct"] == 0.0
    assert out["cash_recommended_pct"] == 100.0
    assert out["gross_scale_factor"] == 1.0
    assert out["rescaled"] is False
    score = out["portfolio_kelly_score"]
    assert score == 0.0
    assert not np.isnan(score)
