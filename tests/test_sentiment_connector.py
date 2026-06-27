"""Tests for gesh_core.sentiment_connector (consensus Phase 5).

Network-free: get_reddit_sentiment is monkeypatched. Covers node_sentiment's
vote mapping, graceful ABSTAIN when Reddit is unavailable, and the cwd/env cache
path resolution (the __file__ gotcha fixed during extraction).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gesh_core import sentiment_connector as sc


def test_module_loads_from_gesh_core():
    assert "gesh_core" in (sc.__file__ or "")


def _stub(monkeypatch, **data):
    monkeypatch.setattr(sc, "get_reddit_sentiment", lambda symbol, **k: data)


def test_node_sentiment_bullish(monkeypatch):
    _stub(monkeypatch, data_source="json_api", overall="BULLISH", sentiment_score=0.42,
          post_count=40, bull_pct=70.0, bear_pct=15.0)
    vote, detail = sc.node_sentiment("NVDA")
    assert vote == sc.VOTE_BULLISH
    assert "Reddit=BULLISH" in detail


def test_node_sentiment_bearish(monkeypatch):
    _stub(monkeypatch, data_source="praw", overall="BEARISH", sentiment_score=-0.3,
          post_count=22, bull_pct=20.0, bear_pct=65.0)
    vote, _ = sc.node_sentiment("NVDA")
    assert vote == sc.VOTE_BEARISH


def test_node_sentiment_neutral(monkeypatch):
    _stub(monkeypatch, data_source="json_api", overall="NEUTRAL", sentiment_score=0.01,
          post_count=10, bull_pct=40.0, bear_pct=40.0)
    vote, _ = sc.node_sentiment("NVDA")
    assert vote == sc.VOTE_NEUTRAL


def test_node_sentiment_abstains_when_unavailable(monkeypatch):
    _stub(monkeypatch, data_source="unavailable", overall="INSUFFICIENT",
          sentiment_score=0.0, post_count=0, bull_pct=0.0, bear_pct=0.0)
    vote, detail = sc.node_sentiment("NVDA")
    assert vote is sc.ABSTAIN
    assert "unavailable" in detail.lower()


def test_node_sentiment_never_raises(monkeypatch):
    monkeypatch.setattr(sc, "get_reddit_sentiment",
                        lambda symbol, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    vote, detail = sc.node_sentiment("NVDA")
    assert vote is sc.ABSTAIN


def test_fetched_at_is_timezone_aware(monkeypatch, tmp_path):
    """fetched_at must be a timezone-aware UTC timestamp (M3).

    The module previously used the deprecated naive datetime.utcnow(); on
    Python >=3.12 that emits a DeprecationWarning and yields a naive timestamp
    that breaks aware/naive comparisons in _cache_valid.
    """
    from datetime import datetime

    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", tmp_path / ".cache.json")
    monkeypatch.setattr(sc, "_fetch_praw", lambda s: [])
    monkeypatch.setattr(sc, "_fetch_json_api", lambda s: [])

    res = sc.get_reddit_sentiment("NVDA", force_refresh=True)
    parsed = datetime.fromisoformat(res["fetched_at"])
    assert parsed.tzinfo is not None, "fetched_at should be timezone-aware (UTC)"


def test_cache_valid_roundtrip_is_fresh(monkeypatch, tmp_path):
    """A freshly written cache entry must read back as valid (M3 regression).

    Guards against an aware/naive subtraction TypeError between the written
    fetched_at and the _cache_valid 'now' that would silently invalidate every
    cache hit and force a refetch on every call.
    """
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", tmp_path / ".cache.json")
    monkeypatch.setattr(sc, "_fetch_praw", lambda s: [])
    monkeypatch.setattr(sc, "_fetch_json_api", lambda s: [])

    sc.get_reddit_sentiment("NVDA", force_refresh=True)  # writes cache
    assert sc._cache_valid("NVDA") is True


def test_cache_path_env_override(monkeypatch, tmp_path):
    target = tmp_path / "s.json"
    monkeypatch.setenv("GESH_SENTIMENT_CACHE", str(target))
    # reload to re-evaluate the module-level cache path
    import importlib
    importlib.reload(sc)
    try:
        assert sc.SENTIMENT_CACHE_FILE == target
    finally:
        monkeypatch.delenv("GESH_SENTIMENT_CACHE", raising=False)
        importlib.reload(sc)
