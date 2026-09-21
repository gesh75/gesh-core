"""Leftover sentiment edges: live-but-insufficient abstain, and cache-hit skip.

node_sentiment must ABSTAIN when overall is INSUFFICIENT even if a live source
returned a score — n<3 is not a vote. get_reddit_sentiment must serve a fresh
cache entry without refetching (force_refresh still bypasses).
"""

from __future__ import annotations

from gesh_core import sentiment_connector as sc


def _stub(monkeypatch, **data):
    monkeypatch.setattr(sc, "get_reddit_sentiment", lambda symbol, **k: data)


def test_node_sentiment_abstains_on_insufficient_even_when_source_is_live(monkeypatch):
    """A json_api/praw payload with n<3 must not become a consensus vote."""
    _stub(
        monkeypatch,
        data_source="json_api",
        overall="INSUFFICIENT",
        sentiment_score=0.80,
        post_count=2,
        bull_pct=100.0,
        bear_pct=0.0,
    )
    vote, detail = sc.node_sentiment("NVDA")
    assert vote is sc.ABSTAIN
    assert "unavailable" in detail.lower()


def test_get_reddit_sentiment_cache_hit_skips_fetch(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", tmp_path / ".cache.json")
    praw_calls = {"n": 0}
    json_calls = {"n": 0}

    def praw(_symbol):
        praw_calls["n"] += 1
        return []

    def json_api(_symbol):
        json_calls["n"] += 1
        return []

    monkeypatch.setattr(sc, "_fetch_praw", praw)
    monkeypatch.setattr(sc, "_fetch_json_api", json_api)

    first = sc.get_reddit_sentiment("NVDA", force_refresh=True)
    assert first["symbol"] == "NVDA"
    assert praw_calls["n"] == 1 and json_calls["n"] == 1

    second = sc.get_reddit_sentiment("NVDA")
    assert second["fetched_at"] == first["fetched_at"]
    assert praw_calls["n"] == 1 and json_calls["n"] == 1


def test_force_refresh_bypasses_valid_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", tmp_path / ".cache.json")
    praw_calls = {"n": 0}
    monkeypatch.setattr(
        sc,
        "_fetch_praw",
        lambda _s: (praw_calls.__setitem__("n", praw_calls["n"] + 1), [])[1],
    )
    monkeypatch.setattr(sc, "_fetch_json_api", lambda _s: [])

    sc.get_reddit_sentiment("NVDA", force_refresh=True)
    sc.get_reddit_sentiment("NVDA", force_refresh=True)
    assert praw_calls["n"] == 2
