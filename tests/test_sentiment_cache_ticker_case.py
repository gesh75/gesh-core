"""Sentiment cache keys are uppercased so mixed-case lookups share one entry.

Relevance of English-word tickers is an open production-fix; this only pins
the cache key. A lowercase ``nvda`` write must satisfy an ``NVDA`` TTL check
or every consensus node refetches Reddit on the next symbol casing.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gesh_core import sentiment_connector as sc


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", tmp_path / "sentiment_cache.json")
    yield


def test_cache_write_and_hit_are_case_insensitive():
    payload = {
        "symbol": "nvda",
        "overall": "BULLISH",
        "sentiment_score": 0.4,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    sc._save_cache("nvda", payload)
    assert sc._cache_valid("NVDA") is True
    assert sc._cache_valid("nvda") is True
    loaded = sc._load_cache("NvDa")
    assert loaded is not None
    assert loaded["overall"] == "BULLISH"
