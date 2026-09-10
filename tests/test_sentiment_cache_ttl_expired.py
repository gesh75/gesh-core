"""A cache entry older than ``CACHE_TTL_M`` must not be treated as fresh.

``_cache_valid`` compares age against 90 minutes. An expired hit that still
returned would freeze Reddit sentiment for the rest of the process lifetime
and starve the consensus node of new crowd signal.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from gesh_core import sentiment_connector as sc


def test_cache_older_than_ttl_is_invalid(monkeypatch, tmp_path):
    cache = tmp_path / ".sentiment_cache.json"
    stale = datetime.now(UTC) - timedelta(minutes=sc.CACHE_TTL_M + 1)
    cache.write_text(
        json.dumps(
            {
                "NVDA": {
                    "symbol": "NVDA",
                    "overall": "BULLISH",
                    "fetched_at": stale.isoformat(),
                }
            }
        )
    )
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", cache)
    assert sc._cache_valid("NVDA") is False


def test_expired_cache_does_not_short_circuit_fetch(monkeypatch, tmp_path):
    cache = tmp_path / ".sentiment_cache.json"
    stale = datetime.now(UTC) - timedelta(minutes=sc.CACHE_TTL_M + 1)
    cache.write_text(
        json.dumps(
            {
                "NVDA": {
                    "symbol": "NVDA",
                    "overall": "BULLISH",
                    "data_source": "json_api",
                    "fetched_at": stale.isoformat(),
                }
            }
        )
    )
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", cache)
    monkeypatch.setattr(sc, "_fetch_praw", lambda s: [])
    monkeypatch.setattr(sc, "_fetch_json_api", lambda s: [])

    result = sc.get_reddit_sentiment("NVDA")
    assert result["overall"] == "INSUFFICIENT"
    assert result["data_source"] == "unavailable"
