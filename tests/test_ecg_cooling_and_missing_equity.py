"""compute_ecg cooling + fail-closed missing-equity paths.

``_classify`` thresholds are already pinned. The full compute path names the
condition that fired (drawdown vs streak) and treats a missing ``equity`` key
as invalid history — the same fail-closed posture as NaN. An empty book must
stay HEALTHY so a flat day does not invent a portfolio halt.
"""
from __future__ import annotations

from gesh_core import ecg


def _hist(equities):
    rows = [{"equity": e, "percent_change": -99.0, "current_price": e} for e in equities]
    return list(reversed(rows))


def test_peak_then_modest_drop_is_cooling_via_drawdown() -> None:
    # 100 → 91 is -9% from peak: COOLING, not SUSPENDED, and the message
    # must name drawdown (not a phantom losing-streak).
    out = ecg.compute_ecg([{"symbol": "AAA", "equity": 91}], lambda s: _hist([100, 91]))
    st = out["states"][0]
    assert st["state"] == "COOLING"
    assert st["drawdown_pct"] == -9.0
    assert "drawdown" in st["message"]
    assert "consecutive" not in st["message"]
    assert out["portfolio_gate"] == "COOLING"


def test_missing_equity_key_fails_closed() -> None:
    out = ecg.compute_ecg(
        [{"symbol": "BAD", "equity": 50}],
        lambda s: [{"percent_change": -1.0, "current_price": 50}],
    )
    st = out["states"][0]
    assert st["state"] == "SUSPENDED"
    assert st["equity_history"] == []
    assert "invalid" in st["message"]
    assert out["portfolio_gate"] == "SUSPENDED"


def test_empty_holdings_portfolio_is_healthy() -> None:
    out = ecg.compute_ecg([], lambda s: _hist([100, 110]))
    assert out["states"] == []
    assert out["portfolio_gate"] == "HEALTHY"
    assert "healthy" in out["portfolio_message"].lower()
