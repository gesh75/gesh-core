"""Pre-M3 naive ``fetched_at`` values are treated as UTC for TTL.

``_cache_valid`` attaches ``tzinfo=UTC`` to naive timestamps so
aware/naive subtraction never raises. A 30-minute-old naive entry stays
fresh; a 91-minute-old naive entry is stale. Pin that so a later reject-
naive change cannot force a refetch storm on leftover on-disk caches.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from gesh_core import sentiment_connector as sc


def _write(path, symbol: str, fetched_at: str) -> None:
    path.write_text(json.dumps({symbol: {"fetched_at": fetched_at, "overall": "NEUTRAL"}}))


def test_naive_timestamp_within_ttl_is_fresh(monkeypatch, tmp_path) -> None:
    cache = tmp_path / ".cache.json"
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", cache)
    now = datetime.now(UTC)
    _write(cache, "NVDA", (now - timedelta(minutes=30)).replace(tzinfo=None).isoformat())
    assert sc._cache_valid("NVDA") is True


def test_naive_timestamp_past_ttl_is_stale(monkeypatch, tmp_path) -> None:
    cache = tmp_path / ".cache.json"
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", cache)
    now = datetime.now(UTC)
    _write(cache, "NVDA", (now - timedelta(minutes=91)).replace(tzinfo=None).isoformat())
    assert sc._cache_valid("NVDA") is False


def test_naive_fresh_cache_skips_fetch(monkeypatch, tmp_path) -> None:
    cache = tmp_path / ".cache.json"
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", cache)
    now = datetime.now(UTC)
    payload = {
        "NVDA": {
            "fetched_at": (now - timedelta(minutes=10)).replace(tzinfo=None).isoformat(),
            "overall": "BULLISH",
            "sentiment_score": 0.4,
            "data_source": "json_api",
            "post_count": 12,
        }
    }
    cache.write_text(json.dumps(payload))

    def _boom(_symbol: str):
        raise AssertionError("fetch must not run on a fresh naive cache hit")

    monkeypatch.setattr(sc, "_fetch_praw", _boom)
    monkeypatch.setattr(sc, "_fetch_json_api", _boom)
    out = sc.get_reddit_sentiment("NVDA", force_refresh=False)
    assert out["overall"] == "BULLISH"
    assert out["sentiment_score"] == 0.4
