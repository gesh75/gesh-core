"""recent_orders / recent_intents are the audit-trail windows the dashboards
read. A silent default-limit or ORDER BY change would hide the newest fills
or flood the UI. Newest-first + default 25 + caller limit are load-bearing.
"""
from __future__ import annotations

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def _intent() -> int:
    state.init_trading_tables()
    return state.log_intent(
        {"symbol": "NVDA", "action": "BUY", "confidence": 1.0, "source": "test"}
    )


def test_recent_orders_default_limit_is_25_newest_first():
    iid = _intent()
    for i in range(30):
        state.log_order(
            iid, None, "paper", f"coid-{i:02d}", "SIMULATED", "NVDA", "BUY", 1, 1.0
        )

    rows = state.recent_orders()
    assert len(rows) == 25
    assert rows[0]["client_order_id"] == "coid-29"
    assert rows[-1]["client_order_id"] == "coid-05"


def test_recent_orders_honors_explicit_limit():
    iid = _intent()
    for i in range(5):
        state.log_order(
            iid, None, "paper", f"ord-{i}", "SIMULATED", "NVDA", "BUY", 1, 1.0
        )

    rows = state.recent_orders(limit=2)
    assert [r["client_order_id"] for r in rows] == ["ord-4", "ord-3"]


def test_recent_intents_default_limit_is_25_newest_first():
    state.init_trading_tables()
    for i in range(30):
        state.log_intent(
            {"symbol": f"S{i:02d}", "action": "HOLD", "confidence": 0.5, "source": "t"}
        )

    rows = state.recent_intents()
    assert len(rows) == 25
    assert rows[0]["symbol"] == "S29"
    assert rows[-1]["symbol"] == "S05"


def test_recent_intents_honors_explicit_limit():
    state.init_trading_tables()
    for sym in ("AAA", "BBB", "CCC"):
        state.log_intent(
            {"symbol": sym, "action": "HOLD", "confidence": 0.5, "source": "t"}
        )

    rows = state.recent_intents(limit=1)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "CCC"
