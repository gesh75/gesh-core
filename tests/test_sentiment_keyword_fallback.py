"""Keyword scoring is the no-VADER path that still feeds node_sentiment.

CI and some hosts have no nltk. The fallback must stay symmetric (bull vs
bear word counts), treat empty/unrelated text as 0, and never raise — a
crash here abstains the whole Reddit node.
"""
from __future__ import annotations

from gesh_core import sentiment_connector as sc


def test_keyword_fallback_scores_bull_and_bear(monkeypatch) -> None:
    monkeypatch.setattr(sc, "_HAS_VADER", False)
    monkeypatch.setattr(sc, "_SIA", None)
    assert sc._score_text("buy long bullish upgrade") > 0
    assert sc._score_text("sell crash dump avoid") < 0


def test_keyword_fallback_empty_or_unrelated_is_zero(monkeypatch) -> None:
    monkeypatch.setattr(sc, "_HAS_VADER", False)
    monkeypatch.setattr(sc, "_SIA", None)
    assert sc._score_text("") == 0.0
    assert sc._score_text("the weather is fine today") == 0.0


def test_keyword_fallback_mixed_cancels(monkeypatch) -> None:
    monkeypatch.setattr(sc, "_HAS_VADER", False)
    monkeypatch.setattr(sc, "_SIA", None)
    # one bull word, one bear word → (1-1)/2 = 0
    assert sc._score_text("buy sell") == 0.0
