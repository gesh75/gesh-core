"""Empty history is HEALTHY (insufficient), and a 0% session breaks a streak.

#61 fail-closes a *missing equity key* to SUSPENDED. An empty history list is
the opposite: not enough data yet, so the gate stays HEALTHY. A flat 0% print
must not count as a loss — otherwise a halt day would keep a cooling streak
alive and trip SUSPENDED after six quiet sessions.
"""
from __future__ import annotations

from gesh_core import ecg


def test_empty_history_is_healthy_insufficient():
    out = ecg.compute_ecg([{"symbol": "NEW", "equity": 100}], lambda _s: [])
    st = out["states"][0]
    assert st["state"] == "HEALTHY"
    assert st["snapshots_available"] == 0
    assert "Insufficient history" in st["message"]
    assert out["portfolio_gate"] == "HEALTHY"


def test_zero_change_breaks_a_loss_streak():
    # 100 → 99 → 99 → 99: one real decline then two flat prints.
    # Newest-first history_fn convention is handled by compute_ecg.
    history = [
        {"equity": 99.0},
        {"equity": 99.0},
        {"equity": 99.0},
        {"equity": 100.0},
    ]
    out = ecg.compute_ecg([{"symbol": "FLAT", "equity": 99.0}], lambda _s: history)
    st = out["states"][0]
    assert st["loss_streak"] == 0
    assert st["state"] == "HEALTHY"
