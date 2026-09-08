"""Portfolio gate is COOLING when the worst holding is COOLING, not HEALTHY.

Main tests pin worst-wins SUSPENDED. A book with only a −9% drawdown
(COOLING band, not SUSPENDED) must raise the portfolio gate so the
dashboard cannot stay HEALTHY while a name is already in the cooling
circuit-breaker.
"""
from __future__ import annotations

from gesh_core import ecg


def _hist(equities):
    rows = [{"equity": e, "percent_change": 0.0, "current_price": e} for e in equities]
    return list(reversed(rows))


def test_cooling_only_book_sets_portfolio_gate_cooling():
    holdings = [
        {"symbol": "OK", "equity": 110},
        {"symbol": "WARM", "equity": 91},
    ]

    def hist(sym):
        return _hist([100, 110]) if sym == "OK" else _hist([100, 91])

    out = ecg.compute_ecg(holdings, hist)
    states = {s["symbol"]: s["state"] for s in out["states"]}
    assert states["OK"] == "HEALTHY"
    assert states["WARM"] == "COOLING"
    assert out["portfolio_gate"] == "COOLING"
    assert "cooling" in out["portfolio_message"].lower()
    assert "SUSPENDED" not in out["portfolio_message"]
