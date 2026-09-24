"""JSON/pandas bools on vote *values* use Python ``True == 1`` / ``False == 0``.

``test_precision_overlay_bool_counts`` pins True/False as *tallies*. A bool on
Rel.Strength or Momentum is a different fail-open: ``True == -1`` is False so
the highest-IC veto never fires, and ``True == 1`` counts as a price confirm.
"""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def _row(votes: dict, *, bullish: int = 4, bearish: int = 0, verdict: str = "BUY") -> dict:
    return {"verdict": verdict, "votes": votes, "bullish": bullish, "bearish": bearish}


def _agreeing(**overrides: object) -> dict:
    votes = {
        "Momentum": 1,
        "Trend": 1,
        "Rel.Strength": 1,
        "Volume": 1,
        "Macro": 1,
    }
    votes.update(overrides)
    return votes


def test_rel_strength_true_does_not_veto() -> None:
    d = precision_overlay_blocks("BUY", _row(_agreeing(**{"Rel.Strength": True})))
    assert d.blocked is False
    assert d.reason == ""


def test_rel_strength_false_does_not_veto() -> None:
    d = precision_overlay_blocks("BUY", _row(_agreeing(**{"Rel.Strength": False})))
    assert d.blocked is False
    assert d.reason == ""


def test_momentum_true_satisfies_price_confirm() -> None:
    d = precision_overlay_blocks("BUY", _row(_agreeing(Momentum=True, Trend=False)))
    assert d.blocked is False


def test_both_price_nodes_false_blocks() -> None:
    d = precision_overlay_blocks("BUY", _row(_agreeing(Momentum=False, Trend=False)))
    assert d.blocked is True
    assert "price confirm" in d.reason.lower() or "Momentum" in d.reason
