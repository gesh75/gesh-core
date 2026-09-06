"""``log_intent`` fills conservative defaults for optional columns and
fail-closes when symbol/action are missing.

A host that logs a partial dict must not invent a ``source='consensus'``
(that would bypass source-based autonomy checks) or a confidence of 1.0.
Missing required keys must raise so the audit chain cannot store a
headless row.
"""
from __future__ import annotations

import pytest

from gesh_core.trading import state


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DB_PATH", tmp_path / "gesh_financial.db")
    yield


def test_log_intent_defaults_source_unknown_and_confidence_zero():
    iid = state.log_intent({"symbol": "NVDA", "action": "HOLD"})
    assert iid > 0
    row = state.recent_intents(limit=1)[0]
    assert row["source"] == "unknown"
    assert row["confidence"] == 0.0
    assert row["time_in_force"] == "day"
    assert row["schema_version"] == 1
    assert row["target_pct"] is None


def test_log_intent_missing_symbol_raises():
    with pytest.raises(KeyError):
        state.log_intent({"action": "HOLD", "source": "manual"})


def test_log_intent_missing_action_raises():
    with pytest.raises(KeyError):
        state.log_intent({"symbol": "NVDA", "source": "manual"})
