"""Sentiment relevance, keyword scoring, and fetch fail-closed paths.

Classification + cache TTL live in other PRs. These pin the filters that decide
which Reddit posts enter the score and the fetch fallbacks that must return []
(never raise) so node_sentiment can ABSTAIN.
"""
from __future__ import annotations

from types import SimpleNamespace

from gesh_core import sentiment_connector as sc


def test_is_relevant_requires_ticker_word_or_cashtag():
    assert sc._is_relevant("I am buying NVDA today", "NVDA") is True
    assert sc._is_relevant("$NVDA to the moon", "nvda") is True
    assert sc._is_relevant("I like NVIDIA but no ticker", "NVDA") is False
    # Word boundary: XNVDA / ANVDA must not count as NVDA.
    assert sc._is_relevant("ticker XNVDA mentioned", "NVDA") is False


def test_is_relevant_escapes_class_share_dot():
    # Without re.escape, BRK.B would match BRKXB (dot = any char).
    assert sc._is_relevant("Bought BRK.B this morning", "BRK.B") is True
    assert sc._is_relevant("Bought BRKXB this morning", "BRK.B") is False


def test_score_text_keyword_fallback(monkeypatch):
    monkeypatch.setattr(sc, "_HAS_VADER", False)
    monkeypatch.setattr(sc, "_SIA", None)
    assert sc._score_text("") == 0.0
    assert sc._score_text("no signal words here") == 0.0
    assert sc._score_text("buy the dip, strong breakout") > 0
    assert sc._score_text("sell the dump, crash incoming") < 0


def test_fetch_praw_without_creds_or_praw_is_empty(monkeypatch):
    monkeypatch.setattr(sc, "_HAS_PRAW", False)
    monkeypatch.setattr(sc, "_ENV", {"REDDIT_CLIENT_ID": "x", "REDDIT_CLIENT_SECRET": "y"})
    assert sc._fetch_praw("NVDA") == []

    monkeypatch.setattr(sc, "_HAS_PRAW", True)
    monkeypatch.setattr(sc, "_ENV", {})
    assert sc._fetch_praw("NVDA") == []


def test_fetch_praw_exception_returns_empty(monkeypatch):
    monkeypatch.setattr(sc, "_HAS_PRAW", True)
    monkeypatch.setattr(
        sc, "_ENV", {"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "secret"}
    )

    class _Boom:
        def __init__(self, **_k):
            raise RuntimeError("praw auth failed")

    monkeypatch.setattr(sc, "praw", SimpleNamespace(Reddit=_Boom), raising=False)
    assert sc._fetch_praw("NVDA") == []


def test_fetch_json_api_rate_limit_and_errors(monkeypatch):
    monkeypatch.setattr(sc.time, "sleep", lambda *_a, **_k: None)
    calls = {"n": 0}

    class _Resp:
        def __init__(self, status: int, payload=None):
            self.status_code = status
            self._payload = payload or {}

        def json(self):
            return self._payload

    def fake_get(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Resp(429)
        raise RuntimeError("timeout")

    monkeypatch.setattr(sc.requests, "get", fake_get)
    assert sc._fetch_json_api("NVDA") == []
    # 429 breaks the inner feed loop for that sub; each remaining sub still
    # tries both feeds and swallows the timeout.
    assert calls["n"] == 1 + 2 * (len(sc.SUBREDDITS) - 1)


def test_fetch_json_api_keeps_relevant_posts(monkeypatch):
    monkeypatch.setattr(sc.time, "sleep", lambda *_a, **_k: None)
    payload = {
        "data": {
            "children": [
                {"data": {"title": "NVDA earnings beat", "selftext": "buy", "score": 12}},
                {"data": {"title": "unrelated chip news", "selftext": "", "score": 99}},
            ]
        }
    }

    class _Resp:
        status_code = 200

        def json(self):
            return payload

    monkeypatch.setattr(sc.requests, "get", lambda *_a, **_k: _Resp())
    posts = sc._fetch_json_api("NVDA")
    assert posts
    assert all("NVDA" in p["text"].upper() for p in posts)
    assert all(p["score"] >= 1 for p in posts)


def test_load_env_reads_dotenv_then_os(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "REDDIT_CLIENT_ID=from-file\n"
        "REDDIT_USER_AGENT=gesh-test/1.0\n"
        "# comment\n"
    )
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "from-os")
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    keys = sc._load_env()
    assert keys["REDDIT_CLIENT_ID"] == "from-file"
    assert keys["REDDIT_CLIENT_SECRET"] == "from-os"
    assert keys["REDDIT_USER_AGENT"] == "gesh-test/1.0"
