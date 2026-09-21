"""Weighted Reddit aggregation: WSB downweight, n<3, score bands, upvote cap.

Keyword scoring is covered elsewhere. These pin the aggregation that turns
posts into a Node 6 vote — a refactor that equal-weights WSB or drops the
n<3 INSUFFICIENT floor silently changes consensus entries.
"""

from __future__ import annotations

from gesh_core import sentiment_connector as sc


def _run(monkeypatch, tmp_path, posts: list[dict]) -> dict:  # noqa: ANN001 — pytest fixtures
    monkeypatch.setattr(sc, "SENTIMENT_CACHE_FILE", tmp_path / ".cache.json")
    monkeypatch.setattr(sc, "_HAS_VADER", False)
    monkeypatch.setattr(sc, "_SIA", None)
    monkeypatch.setattr(sc, "_fetch_praw", lambda s: posts)
    monkeypatch.setattr(sc, "_fetch_json_api", lambda s: [])
    return sc.get_reddit_sentiment("NVDA", force_refresh=True)


def test_fewer_than_three_posts_is_insufficient(monkeypatch, tmp_path):
    posts = [
        {"text": "NVDA buy long moon", "score": 50, "weight": 1.0, "source": "stocks"},
        {"text": "NVDA strong breakout", "score": 40, "weight": 1.0, "source": "investing"},
    ]
    result = _run(monkeypatch, tmp_path, posts)
    assert result["post_count"] == 2
    assert result["overall"] == "INSUFFICIENT"


def test_three_bullish_posts_are_bullish(monkeypatch, tmp_path):
    posts = [
        {"text": "NVDA buy long moon", "score": 20, "weight": 1.0, "source": "stocks"},
        {"text": "NVDA strong breakout", "score": 20, "weight": 1.0, "source": "investing"},
        {"text": "NVDA accumulate growth", "score": 20, "weight": 1.0, "source": "StockMarket"},
    ]
    result = _run(monkeypatch, tmp_path, posts)
    assert result["overall"] == "BULLISH"
    assert result["sentiment_score"] >= 0.15


def test_three_bearish_posts_are_bearish(monkeypatch, tmp_path):
    posts = [
        {"text": "NVDA sell crash dump", "score": 20, "weight": 1.0, "source": "stocks"},
        {"text": "NVDA overvalued avoid", "score": 20, "weight": 1.0, "source": "investing"},
        {"text": "NVDA downgrade miss", "score": 20, "weight": 1.0, "source": "StockMarket"},
    ]
    result = _run(monkeypatch, tmp_path, posts)
    assert result["overall"] == "BEARISH"
    assert result["sentiment_score"] <= -0.15


def test_wsb_weight_cannot_overpower_equal_score_stocks_post(monkeypatch, tmp_path):
    # Same |score| on text; WSB is 0.7× so a WSB-bull / stocks-bear pair must
    # land bearish of the equal-weight pair.
    bull = "NVDA buy long moon strong"
    bear = "NVDA sell crash dump avoid"
    equal = _run(
        monkeypatch,
        tmp_path,
        [
            {"text": bear, "score": 100, "weight": 1.0, "source": "stocks"},
            {"text": bull, "score": 100, "weight": 1.0, "source": "investing"},
            {"text": "NVDA hold", "score": 1, "weight": 1.0, "source": "StockMarket"},
        ],
    )
    wsb_bull = _run(
        monkeypatch,
        tmp_path,
        [
            {"text": bear, "score": 100, "weight": 1.0, "source": "stocks"},
            {"text": bull, "score": 100, "weight": sc.WSB_WEIGHT, "source": "wallstreetbets"},
            {"text": "NVDA hold", "score": 1, "weight": 1.0, "source": "StockMarket"},
        ],
    )
    assert wsb_bull["sentiment_score"] < equal["sentiment_score"]
    assert "wallstreetbets" in wsb_bull["top_sources"]


def test_upvote_weight_caps_so_mega_posts_do_not_unboundedly_dominate(monkeypatch, tmp_path):
    # (score/100)^0.5 is clamped at 10 → score 10_000 and 1_000_000 share a weight.
    text = "NVDA buy long moon strong"
    filler = [
        {"text": "NVDA hold", "score": 1, "weight": 1.0, "source": "investing"},
        {"text": "NVDA hold", "score": 1, "weight": 1.0, "source": "StockMarket"},
    ]
    capped = _run(
        monkeypatch,
        tmp_path,
        [{"text": text, "score": 10_000, "weight": 1.0, "source": "stocks"}, *filler],
    )
    mega = _run(
        monkeypatch,
        tmp_path,
        [{"text": text, "score": 1_000_000, "weight": 1.0, "source": "stocks"}, *filler],
    )
    assert capped["sentiment_score"] == mega["sentiment_score"]
