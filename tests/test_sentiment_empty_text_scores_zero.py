"""Empty or punctuation-only text is a 0 score, not a crash or a vote.

``_score_text`` is the VADER/keyword boundary. Blank bodies are common on
Reddit link posts; they must not count as bearish just because no bull
words fired, and they must not raise into the consensus node.
"""

from __future__ import annotations

from gesh_core import sentiment_connector as sc


def test_empty_and_whitespace_text_score_zero():
    assert sc._score_text("") == 0.0
    assert sc._score_text("   ") == 0.0


def test_punctuation_only_text_score_zero():
    assert sc._score_text("!!! ??? …") == 0.0
