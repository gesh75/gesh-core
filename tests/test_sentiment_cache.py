"""Sentiment cache fail-soft paths not covered by the classification PR.

A stale, naive, or corrupt cache must never raise into consensus. Concurrent
writes must keep sibling symbols (atomic replace).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from gesh_core import sentiment_connector as sc


def test_expired_cache_entry_is_invalid(monkeypatch, tmp_path):
    path = tmp_path / ".cache.json"
    stale = (datetime.now(UTC) - timedelta(minutes=sc.CACHE_TTL_M + 5)).isoformat()
    path.write_text(json.dumps({"NVDA": {"fetched_at": stale, "overall": "BULLISH"}}))
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", path)
    assert sc._cache_valid("NVDA") is False


def test_naive_legacy_timestamp_still_counts_as_fresh(monkeypatch, tmp_path):
    path = tmp_path / ".cache.json"
    naive = datetime.now(UTC).replace(tzinfo=None).isoformat()
    path.write_text(json.dumps({"NVDA": {"fetched_at": naive, "overall": "NEUTRAL"}}))
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", path)
    assert sc._cache_valid("NVDA") is True


def test_corrupt_cache_is_a_miss_not_an_exception(monkeypatch, tmp_path):
    path = tmp_path / ".cache.json"
    path.write_text("{not json")
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", path)
    assert sc._cache_valid("NVDA") is False
    assert sc._load_cache("NVDA") is None


def test_save_cache_preserves_other_symbols(monkeypatch, tmp_path):
    path = tmp_path / ".cache.json"
    path.write_text(json.dumps({"AAPL": {"overall": "BEARISH", "fetched_at": "x"}}))
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", path)
    sc._save_cache("NVDA", {"overall": "BULLISH", "fetched_at": "y"})
    data = json.loads(path.read_text())
    assert data["AAPL"]["overall"] == "BEARISH"
    assert data["NVDA"]["overall"] == "BULLISH"
