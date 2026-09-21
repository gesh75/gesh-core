"""A negative ``KELLY_MAX_GROSS_PCT`` inverts reconciled size and action.

``_max_gross_exposure`` has no range check. When the book still exceeds a
negative cap, ``gross_factor`` is negative, ``_rescale_result`` emits a
negative ``optimal_pct``, and ``_classify_action`` only treats *exact zero*
as AVOID — so a negative target can classify as TRIM. Pin helper + env
path so a later floor-at-zero cannot silently drop inverted dollar deltas.
"""

from __future__ import annotations

import numpy as np
import pytest

from gesh_core import kelly
from gesh_core.kelly import _classify_action, _rescale_result, run_kelly_analysis


def test_rescale_negative_factor_emits_negative_target_and_trim() -> None:
    row = {"symbol": "AAA", "optimal_pct": 10.0, "current_pct": 5.0}
    out = _rescale_result(row, 5_000.0, 100_000.0, corr_haircut=1.0, gross_factor=-0.5)
    assert out["optimal_pct"] == pytest.approx(-5.0)
    assert out["recommended_usd"] == pytest.approx(-5_000.0)
    assert out["delta_usd"] == pytest.approx(-10_000.0)
    assert out["action"] == "TRIM"
    assert row["optimal_pct"] == 10.0  # input not mutated


def test_classify_negative_final_is_not_avoid() -> None:
    action, color = _classify_action(5.0, -5.0)
    assert action == "TRIM"
    assert action != "AVOID"
    assert color == "yellow"


def test_negative_gross_env_inverts_overbet_book(monkeypatch) -> None:
    rng = np.random.default_rng(7)
    drifts = {"AAA": 0.030, "BBB": 0.028, "CCC": 0.026, "DDD": 0.024}
    series = {
        s: (np.full(120, d, dtype=float) + rng.normal(0, 0.01, 120)).astype(float)
        for s, d in drifts.items()
    }
    monkeypatch.setattr(kelly, "_fetch_returns", lambda symbol, days=90: series[symbol])
    monkeypatch.setenv("KELLY_MAX_GROSS_PCT", "-0.50")

    holdings = [
        {"symbol": s, "equity": 1000, "average_buy_price": 10, "current_price": 12} for s in drifts
    ]
    out = run_kelly_analysis(holdings, total_portfolio=100_000)
    assert out["gross_scale_factor"] < 0
    assert out["rescaled"] is True
    assert all(h["optimal_pct"] < 0 for h in out["holdings"])
    assert all(h["action"] != "AVOID" for h in out["holdings"])
