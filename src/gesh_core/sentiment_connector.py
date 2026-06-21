"""
sentiment_connector.py — Live Reddit Sentiment Node (Node 6 replacement)

Replaces the static cached DB news_sentiment node with live crowd
intelligence from Reddit's financial communities.

Subreddits monitored:
  • r/stocks          — retail + semi-professional commentary
  • r/investing       — longer-horizon fundamentals discussion
  • r/wallstreetbets  — momentum / options sentiment (noisy but leading)
  • r/StockMarket     — general market commentary

Scoring method:
  • Collect posts/comments mentioning the ticker (last 48h, hot+new feeds)
  • VADER sentiment analysis on title + body text
  • Upvote-weighted average: higher-voted posts weight more
  • Score normalised to -1 (bearish) → +1 (bullish)
  • WSB posts get 0.7× weight (high noise, still informative directionally)

Setup (optional — works in read-only mode without auth):
    Add to .env:
        REDDIT_CLIENT_ID=your_app_id
        REDDIT_CLIENT_SECRET=your_app_secret
        REDDIT_USER_AGENT=gesh-financial/1.0 by u/your_username

    Get free credentials:
        https://www.reddit.com/prefs/apps → "create another app" → script type

    Without credentials: uses public JSON feed (rate-limited to ~30 req/min)

Fallback chain:
    1. praw (authenticated) → most reliable, 60 req/min
    2. Reddit JSON API (unauthenticated) → works without key, rate-limited
    3. Returns ABSTAIN if both fail

Usage:
    from sentiment_connector import get_reddit_sentiment, node_sentiment

    result = get_reddit_sentiment("NVDA")
    print(result["summary"])

    vote, detail = node_sentiment("NVDA")
"""

from __future__ import annotations

import os
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

# ── Optional praw ─────────────────────────────────────────────────────────────
try:
    import praw
    _HAS_PRAW = True
except ImportError:
    _HAS_PRAW = False

# ── Optional VADER (nltk) — falls back to keyword scoring ────────────────────
try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    _SIA = SentimentIntensityAnalyzer()
    _HAS_VADER = True
except Exception:
    _HAS_VADER = False
    _SIA = None


# ── Config ────────────────────────────────────────────────────────────────────
SUBREDDITS = ["stocks", "investing", "wallstreetbets", "StockMarket"]
WSB_WEIGHT = 0.7          # WSB is noisier — downweight slightly
MAX_POSTS   = 25          # posts per subreddit
CACHE_TTL_M = 90          # cache minutes (sentiment is semi-live)

# gesh-core can't use __file__ (it points inside the package). Cache next to the
# running repo's root (cwd) — both repos run from their own root — or an explicit
# GESH_SENTIMENT_CACHE override.
SENTIMENT_CACHE_FILE = Path(os.getenv("GESH_SENTIMENT_CACHE") or (Path.cwd() / ".sentiment_cache.json"))

# Bullish / bearish keyword fallback (when VADER not available)
_BULL_WORDS = {"buy", "long", "calls", "moon", "bullish", "strong", "undervalued",
               "growth", "beat", "upgrade", "breakout", "hold", "accumulate"}
_BEAR_WORDS = {"sell", "short", "puts", "bearish", "crash", "overvalued",
               "miss", "downgrade", "red", "dump", "avoid", "cut"}


# ── Env key loader ────────────────────────────────────────────────────────────

def _load_env() -> dict[str, str]:
    env_path = Path.cwd() / ".env"   # repos run from their own root where .env lives
    keys = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"):
                if line.startswith(f"{k}="):
                    keys[k] = line.split("=", 1)[1].strip()
    for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"):
        if k not in keys and k in os.environ:
            keys[k] = os.environ[k]
    return keys

_ENV = _load_env()


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _cache_valid(symbol: str) -> bool:
    if not SENTIMENT_CACHE_FILE.exists():
        return False
    try:
        data = json.loads(SENTIMENT_CACHE_FILE.read_text())
        entry = data.get(symbol.upper())
        if not entry:
            return False
        fetched = datetime.fromisoformat(entry["fetched_at"])
        return (datetime.utcnow() - fetched).total_seconds() < CACHE_TTL_M * 60
    except Exception:
        return False


def _load_cache(symbol: str) -> dict | None:
    try:
        data = json.loads(SENTIMENT_CACHE_FILE.read_text())
        return data.get(symbol.upper())
    except Exception:
        return None


def _save_cache(symbol: str, result: dict) -> None:
    try:
        data = {}
        if SENTIMENT_CACHE_FILE.exists():
            try:
                data = json.loads(SENTIMENT_CACHE_FILE.read_text())
            except Exception:
                data = {}
        data[symbol.upper()] = result
        SENTIMENT_CACHE_FILE.write_text(json.dumps(data, default=str))
    except Exception:
        pass


# ── Sentiment scoring ─────────────────────────────────────────────────────────

def _score_text(text: str) -> float:
    """Return sentiment score -1 to +1 for a piece of text."""
    if not text:
        return 0.0
    if _HAS_VADER and _SIA:
        return _SIA.polarity_scores(text)["compound"]
    # Keyword fallback
    words = set(re.findall(r"\b\w+\b", text.lower()))
    bull = len(words & _BULL_WORDS)
    bear = len(words & _BEAR_WORDS)
    total = bull + bear
    if total == 0:
        return 0.0
    return (bull - bear) / total


def _is_relevant(text: str, symbol: str) -> bool:
    """Check if text meaningfully mentions the ticker (not just noise)."""
    sym = symbol.upper()
    # Match $NVDA, NVDA, or full company tickers
    patterns = [
        rf"\${sym}\b",
        rf"\b{sym}\b",
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


# ── Reddit fetch via praw ────────────────────────────────────────────────────

def _fetch_praw(symbol: str) -> list[dict]:
    """Fetch relevant posts via authenticated praw."""
    if not _HAS_PRAW:
        return []
    cid = _ENV.get("REDDIT_CLIENT_ID")
    csec = _ENV.get("REDDIT_CLIENT_SECRET")
    ua   = _ENV.get("REDDIT_USER_AGENT", f"gesh-financial/1.0")
    if not cid or not csec:
        return []
    try:
        reddit = praw.Reddit(
            client_id=cid,
            client_secret=csec,
            user_agent=ua,
        )
        posts = []
        for sub_name in SUBREDDITS:
            weight = WSB_WEIGHT if sub_name == "wallstreetbets" else 1.0
            sub = reddit.subreddit(sub_name)
            for post in sub.search(f"{symbol} OR ${symbol}", limit=MAX_POSTS,
                                   sort="hot", time_filter="week"):
                text = f"{post.title} {post.selftext or ''}"
                if not _is_relevant(text, symbol):
                    continue
                posts.append({
                    "text":   text[:2000],
                    "score":  max(post.score, 1),
                    "weight": weight,
                    "source": sub_name,
                })
        return posts
    except Exception:
        return []


def _fetch_json_api(symbol: str) -> list[dict]:
    """Fetch via Reddit's unauthenticated JSON feed (rate-limited)."""
    posts = []
    headers = {"User-Agent": "gesh-financial/1.0"}
    for sub_name in SUBREDDITS:
        weight = WSB_WEIGHT if sub_name == "wallstreetbets" else 1.0
        for feed in ("hot", "new"):
            try:
                url = f"https://www.reddit.com/r/{sub_name}/search.json"
                params = {
                    "q": f"{symbol} OR ${symbol}",
                    "restrict_sr": "on",
                    "sort": feed,
                    "t": "week",
                    "limit": 15,
                }
                resp = requests.get(url, params=params, headers=headers, timeout=8)
                if resp.status_code == 429:
                    break  # rate limited — stop trying
                if resp.status_code != 200:
                    continue
                items = resp.json().get("data", {}).get("children", [])
                for item in items:
                    d = item.get("data", {})
                    text = f"{d.get('title', '')} {d.get('selftext', '')}"
                    if not _is_relevant(text, symbol):
                        continue
                    posts.append({
                        "text":   text[:2000],
                        "score":  max(int(d.get("score", 1)), 1),
                        "weight": weight,
                        "source": sub_name,
                    })
                time.sleep(0.5)  # polite delay for unauthenticated
            except Exception:
                continue
    return posts


# ── Main sentiment fetch ──────────────────────────────────────────────────────

def get_reddit_sentiment(symbol: str, force_refresh: bool = False) -> dict[str, Any]:
    """
    Fetch and score Reddit sentiment for a ticker symbol.

    Returns
    -------
    {
      "symbol":         str,
      "post_count":     int,
      "sentiment_score":float,   # -1 to +1
      "overall":        str,     # BULLISH / NEUTRAL / BEARISH / INSUFFICIENT
      "bull_pct":       float,   # % of bullish posts
      "bear_pct":       float,
      "top_sources":    list[str],
      "data_source":    str,     # "praw" | "json_api" | "unavailable"
      "summary":        str,     # Claude-injectable text
      "fetched_at":     str,
    }
    """
    sym = symbol.upper()

    if not force_refresh and _cache_valid(sym):
        cached = _load_cache(sym)
        if cached:
            return cached

    result: dict[str, Any] = {
        "symbol":          sym,
        "post_count":      0,
        "sentiment_score": 0.0,
        "overall":         "INSUFFICIENT",
        "bull_pct":        0.0,
        "bear_pct":        0.0,
        "top_sources":     [],
        "data_source":     "unavailable",
        "summary":         f"## Reddit Sentiment ({sym})\n  • No data available",
        "fetched_at":      datetime.utcnow().isoformat(),
    }

    # Try praw first, fall back to JSON API
    posts = _fetch_praw(sym)
    if posts:
        result["data_source"] = "praw"
    else:
        posts = _fetch_json_api(sym)
        if posts:
            result["data_source"] = "json_api"

    if not posts:
        _save_cache(sym, result)
        return result

    # ── Weighted sentiment aggregation ────────────────────────────────────────
    total_weight = 0.0
    weighted_score = 0.0
    bull_count = 0
    bear_count = 0
    source_counts: dict[str, int] = {}

    for p in posts:
        text_score = _score_text(p["text"])
        # Upvote weight: log-scale to prevent mega-posts dominating
        upvote_w = 1.0 + 0.3 * min(10.0, (p["score"] / 100) ** 0.5)
        w = p["weight"] * upvote_w

        weighted_score += text_score * w
        total_weight   += w

        if text_score > 0.05:
            bull_count += 1
        elif text_score < -0.05:
            bear_count += 1

        src = p["source"]
        source_counts[src] = source_counts.get(src, 0) + 1

    final_score = weighted_score / total_weight if total_weight > 0 else 0.0
    final_score = max(-1.0, min(1.0, final_score))

    n = len(posts)
    bull_pct = round(bull_count / n * 100, 1)
    bear_pct = round(bear_count / n * 100, 1)

    if n < 3:
        overall = "INSUFFICIENT"
    elif final_score >= 0.15:
        overall = "BULLISH"
    elif final_score <= -0.15:
        overall = "BEARISH"
    else:
        overall = "NEUTRAL"

    top_sources = sorted(source_counts, key=source_counts.get, reverse=True)[:3]

    result.update({
        "post_count":      n,
        "sentiment_score": round(final_score, 3),
        "overall":         overall,
        "bull_pct":        bull_pct,
        "bear_pct":        bear_pct,
        "top_sources":     top_sources,
    })

    src_label = "PRAW" if result["data_source"] == "praw" else "Reddit JSON"
    lines = [f"## Reddit Sentiment ({sym}) [{src_label}]"]
    lines.append(f"  Overall: {overall}  |  Score: {final_score:+.3f}  |  Posts: {n}")
    lines.append(f"  Bull: {bull_pct:.0f}%  Bear: {bear_pct:.0f}%  |  Sources: {', '.join(top_sources)}")
    result["summary"] = "\n".join(lines)

    _save_cache(sym, result)
    return result


# ── Consensus node function ───────────────────────────────────────────────────

VOTE_BULLISH =  1
VOTE_NEUTRAL =  0
VOTE_BEARISH = -1
ABSTAIN      = None


def node_sentiment(symbol: str) -> tuple[int | None, str]:
    """
    Node 6 — Live Reddit Sentiment consensus vote.

    Replaces node_news() in consensus.py run_consensus_holding().
    Already called from there via the updated node_news() wrapper.
    """
    try:
        data = get_reddit_sentiment(symbol)

        if data["data_source"] == "unavailable" or data["overall"] == "INSUFFICIENT":
            return ABSTAIN, f"Reddit unavailable for {symbol} (set REDDIT_CLIENT_ID in .env)"

        score   = data["sentiment_score"]
        overall = data["overall"]
        n       = data["post_count"]
        bull    = data["bull_pct"]
        bear    = data["bear_pct"]

        detail = (
            f"Reddit={overall} Score={score:+.3f} "
            f"Posts={n} Bull={bull:.0f}% Bear={bear:.0f}%"
        )

        if overall == "BULLISH":   return VOTE_BULLISH, detail
        if overall == "BEARISH":   return VOTE_BEARISH, detail
        return VOTE_NEUTRAL, detail

    except Exception as e:
        return ABSTAIN, f"Sentiment node error: {e}"


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    print(f"Fetching Reddit sentiment for {sym}...\n")

    # Check config
    cid = _ENV.get("REDDIT_CLIENT_ID", "")
    print(f"  Mode: {'praw (authenticated)' if cid else 'JSON API (unauthenticated)'}")
    print(f"  VADER: {'available' if _HAS_VADER else 'not installed — using keyword fallback'}\n")

    result = get_reddit_sentiment(sym, force_refresh=True)
    print(result["summary"])
    print(f"\n  Sentiment Score : {result['sentiment_score']:+.3f}")
    print(f"  Overall         : {result['overall']}")
    print(f"  Post Count      : {result['post_count']}")
    print(f"  Data Source     : {result['data_source']}")

    vote, detail = node_sentiment(sym)
    vote_map = {1: "BULLISH", 0: "NEUTRAL", -1: "BEARISH", None: "ABSTAIN"}
    print(f"\nNode 6 Vote: {vote_map.get(vote, 'ABSTAIN')} — {detail}")

    if not _HAS_VADER:
        print("\n  Tip: pip install nltk && python3 -c \"import nltk; nltk.download('vader_lexicon')\"")
        print("       for more accurate sentiment scoring.")
