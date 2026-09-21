"""A truncated cache file must not poison the next write.

Concurrent consensus runs share `.sentiment_cache.json`. A crashed writer can
leave truncated JSON; `_save_cache` must treat that as empty and still persist
the new symbol so later reads do not raise into Node 6.
"""

from __future__ import annotations

import json

from gesh_core import sentiment_connector as sc


def test_save_cache_over_truncated_json_does_not_raise(monkeypatch, tmp_path) -> None:
    path = tmp_path / ".cache.json"
    path.write_text("{truncated")
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", path)

    payload = {"overall": "NEUTRAL", "fetched_at": "2026-09-01T10:00:00+00:00"}
    sc._save_cache("NVDA", payload)

    data = json.loads(path.read_text())
    assert data["NVDA"] == payload


def test_save_cache_write_failure_is_not_fatal(monkeypatch, tmp_path) -> None:
    path = tmp_path / "missing-dir" / ".cache.json"
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", path)
    sc._save_cache("NVDA", {"overall": "BULLISH"})  # must not raise
