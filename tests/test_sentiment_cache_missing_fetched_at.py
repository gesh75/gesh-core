"""Leftover sentiment cache: a row without fetched_at is stale.

#58 pins truncated-cache rewrite; #55 pins a well-formed cache hit. A legacy
or hand-edited entry that has a score but no timestamp must not be treated as
fresh — that would serve a never-expiring sentiment vote into consensus.
"""

from __future__ import annotations

import json

from gesh_core import sentiment_connector as sc


def test_cache_entry_without_fetched_at_is_stale(monkeypatch, tmp_path) -> None:
    path = tmp_path / ".sentiment_cache.json"
    path.write_text(json.dumps({"NVDA": {"score": 0.9, "summary": "legacy"}}))
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", path)
    assert sc._cache_valid("NVDA") is False
    assert sc._cache_valid("nvda") is False
