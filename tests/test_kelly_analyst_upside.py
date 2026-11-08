"""Analyst-upside boost on Kelly size — money at risk, previously untested.

``kelly_size_holding`` scales the blended Kelly by ``min(upside/100 * 0.2, 0.2)``.
A missing cap would let a 200% "upside" inflate the position by 40% instead of
the disclosed +20%.
"""

from __future__ import annotations

import numpy as np
import pytest

from gesh_core.kelly import kelly_size_holding

rng = np.random.default_rng(42)
POSITIVE_DRIFT = (rng.normal(0.002, 0.01, 120)).astype(float)


def _size(**overrides: object) -> dict:
    kwargs: dict = {
        "symbol": "X",
        "current_equity": 1_000,
        "total_portfolio": 100_000,
        "avg_cost": 10,
        "current_price": 12,
        "returns": POSITIVE_DRIFT,
    }
    kwargs.update(overrides)
    return kelly_size_holding(**kwargs)  # type: ignore[arg-type]


def test_positive_upside_increases_raw_kelly() -> None:
    base = _size()
    boosted = _size(analyst_upside_pct=50)
    assert "error" not in base and "error" not in boosted
    assert boosted["raw_kelly"] > base["raw_kelly"]
    assert boosted["analyst_upside"] == 50
    # 50% upside → +10% raw (0.5 * 0.2), before the half-Kelly / hard cap.
    assert boosted["raw_kelly"] == pytest.approx(base["raw_kelly"] * 1.1, abs=0.15)


def test_upside_boost_caps_at_twenty_percent() -> None:
    at_cap = _size(analyst_upside_pct=100)
    over_cap = _size(analyst_upside_pct=200)
    base = _size()
    assert at_cap["raw_kelly"] == pytest.approx(over_cap["raw_kelly"])
    assert at_cap["raw_kelly"] == pytest.approx(base["raw_kelly"] * 1.2, abs=0.15)


def test_zero_or_negative_upside_does_not_boost() -> None:
    base = _size()
    assert _size(analyst_upside_pct=0)["raw_kelly"] == pytest.approx(base["raw_kelly"])
    assert _size(analyst_upside_pct=-25)["raw_kelly"] == pytest.approx(base["raw_kelly"])
    assert _size(analyst_upside_pct=None)["raw_kelly"] == pytest.approx(base["raw_kelly"])
