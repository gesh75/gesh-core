"""compute_ecg must name a 3-session losing streak as COOLING even when
peak-to-trough drawdown stays inside the -8% band. The Risk tab used to
blame a tiny drawdown for a streak trip; a regression here mislabels the
portfolio gate.
"""
from __future__ import annotations

from gesh_core import ecg


def _hist(equities):
    rows = [{"equity": e, "percent_change": -99.0, "current_price": e} for e in equities]
    return list(reversed(rows))


def test_three_small_declines_cool_via_streak_not_drawdown():
    holdings = [{"symbol": "CCC", "equity": 97}]
    out = ecg.compute_ecg(holdings, lambda s: _hist([100, 99, 98, 97]))
    st = out["states"][0]

    assert st["loss_streak"] == 3
    assert st["state"] == "COOLING"
    assert st["drawdown_pct"] > -8.0
    assert "consecutive losing snapshots" in st["message"]
    assert "drawdown" not in st["message"]
    assert out["portfolio_gate"] == "COOLING"
    assert "cooling" in out["portfolio_message"].lower()
