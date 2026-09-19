"""Residual paper qty at the 1e-9 flatten threshold must disappear.

Floating-point closes often leave a dust remainder. The book treats
``qty > 1e-9`` as still open; anything at or below that is omitted so the
next BUY is a fresh average-cost lot, not an add onto a phantom residual.
"""

from __future__ import annotations

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def _fill(*, symbol: str, fill_qty: float, client_order_id: str) -> None:
    iid = state.log_intent(
        {"symbol": symbol, "action": "BUY", "confidence": 1.0, "source": "test"}
    )
    state.log_order(
        iid,
        None,
        "paper",
        client_order_id,
        "SIMULATED",
        symbol,
        "BUY",
        qty=fill_qty,
        target_price=100.0,
        fill_price=100.0,
        fill_qty=fill_qty,
    )


def test_qty_at_flatten_threshold_is_omitted() -> None:
    _fill(symbol="DUST", fill_qty=1e-9, client_order_id="dust")
    assert "DUST" not in state.paper_open_positions()


def test_qty_above_flatten_threshold_is_kept() -> None:
    _fill(symbol="KEEP", fill_qty=1e-6, client_order_id="keep")
    book = state.paper_open_positions()
    assert book["KEEP"]["qty"] == pytest.approx(1e-6)
    assert book["KEEP"]["avg_cost"] == 100.0
