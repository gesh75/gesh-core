"""+Inf equity with a valid price is persisted — only price is filtered.

ECG later fail-closes on non-finite history, but the row is already in the
book. Pin persistence so a later price-style finite check cannot land
unnoticed, and so callers know inf equity is not skipped today.
"""

from __future__ import annotations

import math

import pytest

from gesh_core import db


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "gesh_financial.db")
    db.init_db()
    yield


def test_inf_equity_with_valid_price_is_written() -> None:
    db.log_equity_snapshot(
        [{"symbol": "INF", "equity": float("inf"), "percent_change": 0.0, "current_price": 10.0}]
    )
    hist = db.get_equity_history("INF")
    assert len(hist) == 1
    assert math.isinf(hist[0]["equity"])
    assert hist[0]["current_price"] == 10.0
