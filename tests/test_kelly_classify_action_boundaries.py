"""Kelly ADD/TRIM cutoffs are exclusive inequalities.

``_classify_action`` (and the inlined copy inside ``kelly_size_holding``)
uses ``current > final * 1.3`` and ``current < final * 0.6``. Landing
exactly on either multiple is HOLD. A later off-by-one rewrite would
churn every name sitting on the band.
"""
from __future__ import annotations

from gesh_core.kelly import _classify_action


def test_exact_trim_multiple_is_hold() -> None:
    action, color = _classify_action(13.0, 10.0)  # 13 == 10 * 1.3
    assert action == "HOLD"
    assert color == "cyan"


def test_just_over_trim_multiple_is_trim() -> None:
    action, color = _classify_action(13.0001, 10.0)
    assert action == "TRIM"
    assert color == "yellow"


def test_exact_add_multiple_is_hold() -> None:
    action, color = _classify_action(6.0, 10.0)  # 6 == 10 * 0.6
    assert action == "HOLD"


def test_just_under_add_multiple_is_add() -> None:
    action, color = _classify_action(5.999, 10.0)
    assert action == "ADD"
    assert color == "green"


def test_zero_target_is_avoid_regardless_of_current() -> None:
    assert _classify_action(50.0, 0.0) == ("AVOID", "red")
    assert _classify_action(0.0, 0.0) == ("AVOID", "red")
