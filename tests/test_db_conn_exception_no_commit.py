"""db._conn() must not persist writes when the caller raises.

Unlike trading.state._conn (which rolls back explicitly), db._conn only
commits after a successful yield. An exception mid-write has to leave the
analysis/equity tables unchanged — otherwise a failed snapshot can poison
ECG history.
"""
from __future__ import annotations

import pytest

from gesh_core import db


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "gesh_financial.db")
    db.init_db()
    yield


def test_exception_inside_conn_does_not_commit_analysis_row() -> None:
    with pytest.raises(RuntimeError, match="boom"):
        with db._conn() as con:
            con.execute(
                "INSERT INTO analysis_runs (run_at, model, portfolio_score) "
                "VALUES ('2026-09-04T00:00:00+00:00', 'sonnet', 1)"
            )
            raise RuntimeError("boom")

    assert db.get_analysis_history() == []
    assert db.get_analysis_by_id(1) is None
