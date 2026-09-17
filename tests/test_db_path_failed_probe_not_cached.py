"""R7 leftover: a failed writable probe must not be remembered as OK.

#83 pins the success-path cache (second ensure_db_writable skips the probe).
If a corrupt/unwritable path were added to `_writable_ok` on the exception
path, a later repair of the same file would still be treated as writable and
the daily-loss book would keep failing closed — or worse, a failed probe
would be skipped and callers would open a broken file.
"""

from __future__ import annotations

import sqlite3

import pytest

from gesh_core import db_path


def test_failed_probe_is_not_cached_and_retry_sees_repair(tmp_path, monkeypatch) -> None:
    target = tmp_path / "repair.db"
    target.write_bytes(b"not a sqlite database")
    monkeypatch.setenv("GESH_DB_PATH", str(target))
    key = str(target)

    db_path._writable_ok.discard(key)
    with pytest.raises(sqlite3.DatabaseError):
        db_path.ensure_db_writable(target)
    assert key not in db_path._writable_ok

    target.unlink()
    repaired = db_path.ensure_db_writable(target)
    assert repaired == target
    assert key in db_path._writable_ok
    con = sqlite3.connect(target)
    try:
        con.execute("SELECT 1")
    finally:
        con.close()
