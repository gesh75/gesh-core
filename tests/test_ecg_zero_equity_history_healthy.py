"""Leftover ECG public path: a measured $0 series is HEALTHY, not SUSPENDED.

The helper already pins peak<=0 → 0% drawdown. compute_ecg must use that
guard on a two-point zero book (enough snapshots to classify) so a cash-flat
name does not fail-closed into SUSPENDED and trip the portfolio gate.
"""

from __future__ import annotations

from gesh_core import ecg


def _hist(equities: list[float]) -> list[dict]:
    return [
        {"snapshot_at": f"2026-01-{i + 1:02d}", "equity": eq, "percent_change": 0.0}
        for i, eq in enumerate(equities)
    ]


def test_zero_equity_history_classifies_healthy() -> None:
    out = ecg.compute_ecg([{"symbol": "CASH", "equity": 0}], lambda s: _hist([0.0, 0.0]))
    st = out["states"][0]
    assert st["state"] == "HEALTHY"
    assert st["drawdown_pct"] == 0.0
    assert st["loss_streak"] == 0
    assert out["portfolio_gate"] == "HEALTHY"
