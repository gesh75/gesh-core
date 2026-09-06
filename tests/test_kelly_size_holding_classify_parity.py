"""The action bands inside ``kelly_size_holding`` must stay locked to
``_classify_action``.

``_classify_action`` is what ``run_kelly_analysis`` uses after the haircut /
gross-cap rescale. The per-name sizer inlines the same exclusive 1.3 / 0.6
cutoffs. If only one copy is edited, the dashboard TRIM/ADD list diverges from
the row the host just sized — the leftover gap after #61 pinned the helper.
"""
from __future__ import annotations

import numpy as np

from gesh_core.kelly import _classify_action, kelly_size_holding

_RNG = np.random.default_rng(42)
POSITIVE_DRIFT = _RNG.normal(0.002, 0.01, 120).astype(float)
NEGATIVE_DRIFT = _RNG.normal(-0.003, 0.01, 120).astype(float)
TOTAL = 100_000.0


def _action(current_equity: float, returns: np.ndarray) -> tuple[str, str, str, str]:
    row = kelly_size_holding(
        "X", current_equity, TOTAL, avg_cost=10.0, current_price=12.0, returns=returns
    )
    current_frac = current_equity / TOTAL
    final_frac = row["recommended_usd"] / TOTAL
    helper_action, helper_color = _classify_action(current_frac, final_frac)
    return row["action"], helper_action, row["action_color"], helper_color


def test_negative_edge_is_avoid_on_both_copies():
    sized, helper, color, helper_color = _action(1_000.0, NEGATIVE_DRIFT)
    assert sized == helper == "AVOID"
    assert color == helper_color == "red"


def test_zero_current_positive_edge_is_add_on_both_copies():
    sized, helper, color, helper_color = _action(0.0, POSITIVE_DRIFT)
    assert sized == helper == "ADD"
    assert color == helper_color == "green"


def test_current_near_optimal_is_hold_on_both_copies():
    base = kelly_size_holding(
        "X", 0.0, TOTAL, avg_cost=10.0, current_price=12.0, returns=POSITIVE_DRIFT
    )
    at_target = base["recommended_usd"]
    assert at_target > 0
    sized, helper, color, helper_color = _action(at_target, POSITIVE_DRIFT)
    assert sized == helper == "HOLD"
    assert color == helper_color == "cyan"


def test_heavily_overweight_is_trim_on_both_copies():
    base = kelly_size_holding(
        "X", 0.0, TOTAL, avg_cost=10.0, current_price=12.0, returns=POSITIVE_DRIFT
    )
    overweight = base["recommended_usd"] * 2.0
    assert overweight > 0
    sized, helper, color, helper_color = _action(overweight, POSITIVE_DRIFT)
    assert sized == helper == "TRIM"
    assert color == helper_color == "yellow"
