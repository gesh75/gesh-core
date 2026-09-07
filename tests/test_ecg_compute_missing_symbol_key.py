"""A holding missing ``symbol`` aborts the entire ECG pass.

``compute_ecg`` subscripts ``h["symbol"]`` before the equity-validation
try/except. Malformed history is fail-closed SUSPENDED per row; a missing
symbol raises ``KeyError`` and prevents any ``portfolio_gate`` from being
returned — including for other valid holdings. Pin the crash so a later
per-row skip cannot silently change the circuit-breaker contract.
"""
from __future__ import annotations

import pytest

from gesh_core import ecg


def _hist(equities):
    rows = [{"equity": e, "percent_change": 0.0, "current_price": e} for e in equities]
    return list(reversed(rows))


def test_missing_symbol_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        ecg.compute_ecg([{"equity": 100}], lambda _s: _hist([100, 110]))


def test_mixed_book_does_not_return_a_portfolio_gate() -> None:
    holdings = [{"symbol": "OK", "equity": 110}, {"equity": 70}]
    with pytest.raises(KeyError):
        ecg.compute_ecg(holdings, lambda s: _hist([100, 110]))


def test_missing_equity_key_in_history_is_per_row_suspended() -> None:
    # Contrast: symbol present, history row missing equity → isolated SUSPENDED.
    out = ecg.compute_ecg(
        [{"symbol": "BAD-DATA", "equity": 70}],
        lambda _s: [{"percent_change": 0.0}],
    )
    assert out["states"][0]["state"] == "SUSPENDED"
    assert out["portfolio_gate"] == "SUSPENDED"
