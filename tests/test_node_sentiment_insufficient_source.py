"""INSUFFICIENT crowd data abstains even when a live source answered.

``node_sentiment`` treats ``overall == "INSUFFICIENT"`` the same as an
unavailable feed — n<3 posts is data coverage, not a NEUTRAL vote. A
later mapping of INSUFFICIENT → 0 would let thin Reddit threads swing
consensus.
"""

from __future__ import annotations

from gesh_core import sentiment_connector as sc


def test_insufficient_with_live_source_abstains(monkeypatch):
    monkeypatch.setattr(
        sc,
        "get_reddit_sentiment",
        lambda symbol, **k: {
            "data_source": "json_api",
            "overall": "INSUFFICIENT",
            "sentiment_score": 0.4,
            "post_count": 2,
            "bull_pct": 100.0,
            "bear_pct": 0.0,
        },
    )
    vote, detail = sc.node_sentiment("NVDA")
    assert vote is sc.ABSTAIN
    assert "unavailable" in detail.lower()
