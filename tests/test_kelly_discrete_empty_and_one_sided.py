"""_discrete_kelly empty / one-sided series must not divide-by-zero.

Win-rate Kelly uses avg_win / avg_loss. An empty series, an all-win series,
or an all-loss series hits the 0.01 fallback so a degenerate book cannot
NaN the blended size that consensus consumes.
"""
from __future__ import annotations

import numpy as np
import pytest

from gesh_core.kelly import _discrete_kelly


def test_empty_returns_use_neutral_win_rate_and_unit_payoff() -> None:
    out = _discrete_kelly(np.array([], dtype=float))
    assert out["win_rate"] == pytest.approx(50.0)
    assert out["payoff_ratio"] == pytest.approx(1.0)
    assert out["kelly_pct"] == pytest.approx(0.0)
    assert np.isfinite(out["kelly_pct"])


def test_all_wins_uses_avg_loss_floor() -> None:
    wins = np.array([0.02, 0.03, 0.04], dtype=float)
    out = _discrete_kelly(wins)
    assert out["win_rate"] == pytest.approx(100.0)
    # avg_loss fallback 0.01 → R = 0.03 / 0.01 = 3; f* = 1 - 0/3 = 1
    assert out["avg_loss_pct"] == pytest.approx(1.0)
    assert out["kelly_pct"] == pytest.approx(1.0)


def test_all_losses_uses_avg_win_floor() -> None:
    losses = np.array([-0.02, -0.04, -0.06], dtype=float)
    out = _discrete_kelly(losses)
    assert out["win_rate"] == pytest.approx(0.0)
    # avg_win fallback 0.01 → R = 0.01 / 0.04 = 0.25; f* = 0 - 1/0.25 = -4
    assert out["avg_win_pct"] == pytest.approx(1.0)
    assert out["kelly_pct"] == pytest.approx(-4.0)
    assert np.isfinite(out["kelly_pct"])
