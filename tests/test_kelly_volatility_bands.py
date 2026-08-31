"""Pin the annualized-vol tier cutoffs used in Kelly sizing output.

The existing parity test only asserted the label is one of four strings.
TRIM/HOLD/AVOID dashboards and the volatility_tier field depend on the actual
30 / 60 / 100 annualized-percent bands.
"""

from __future__ import annotations

import numpy as np
import pytest

from gesh_core import kelly
from gesh_core.kelly import _volatility_score, run_kelly_analysis


def _signed_series(ann_vol_pct: float, n: int = 100) -> np.ndarray:
    """Near-zero-mean series whose population std annualizes to *ann_vol_pct*."""
    daily = ann_vol_pct / (100.0 * np.sqrt(252.0))
    return np.array([daily, -daily] * (n // 2), dtype=float)


@pytest.mark.parametrize(
    ("ann_vol_pct", "expected"),
    [
        (20.0, "LOW"),
        (45.0, "MEDIUM"),
        (80.0, "HIGH"),
        (120.0, "EXTREME"),
    ],
)
def test_volatility_score_bands(ann_vol_pct: float, expected: str):
    assert _volatility_score(_signed_series(ann_vol_pct)) == expected


def test_run_kelly_analysis_applies_analyst_upside_and_ai_verdict(monkeypatch):
    """Portfolio path must thread analyst_targets / ai_verdicts into per-name size.

    The series is a modest 51/49 edge so half-Kelly stays under the 25% cap.
    A high-edge draw hits the cap on every path and the size comparisons
    become vacuous (base == boosted == penalized).
    """
    modest = np.array([0.005] * 51 + [-0.005] * 49, dtype=float)
    monkeypatch.setattr(kelly, "_fetch_returns", lambda symbol, days=90: modest)

    holdings = [{"symbol": "AAA", "equity": 1000, "average_buy_price": 10, "current_price": 12}]
    base = run_kelly_analysis(holdings, total_portfolio=100_000)
    boosted = run_kelly_analysis(
        holdings, total_portfolio=100_000, analyst_targets={"AAA": {"upside_pct": 80}}
    )
    penalized = run_kelly_analysis(
        holdings, total_portfolio=100_000, ai_verdicts={"AAA": {"verdict": "AVOID"}}
    )

    base_pct = base["holdings"][0]["optimal_pct"]
    assert 0 < base_pct < 25.0
    assert boosted["holdings"][0]["optimal_pct"] > base_pct
    assert boosted["holdings"][0]["analyst_upside"] == 80
    assert penalized["holdings"][0]["optimal_pct"] < base_pct
    assert penalized["holdings"][0]["ai_penalty"] == 0.5
