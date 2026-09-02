"""log_order currently returns a missing lastrowid instead of failing closed.

``_insert_intent`` and ``log_decision`` raise DatabaseError when SQLite reports
no row ID. The order insert is the last link of the intent→decision→order
audit chain and today returns None. Pin that asymmetry so a later fail-closed
change is deliberate.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from gesh_core.trading import state


def test_log_order_returns_none_when_lastrowid_missing(monkeypatch) -> None:
    con = MagicMock()
    con.execute.return_value.lastrowid = None
    con.__enter__.return_value = con
    con.__exit__.return_value = False
    monkeypatch.setattr(state, "_conn", lambda: con)

    oid = state.log_order(
        1, 2, "paper", "cid-1", "SIMULATED", "NVDA", "BUY", 1.0, 100.0
    )
    assert oid is None
    con.execute.assert_called_once()
