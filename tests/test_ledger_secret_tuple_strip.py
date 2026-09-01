"""Secret stripping must walk tuples, not only lists and dicts.

AI payloads sometimes arrive as a tuple of score rows. A stripper that
only recurses lists would leave ``api_key`` / ``token`` in the stored
allowlisted JSON and into the ledger hash.
"""

from __future__ import annotations

from gesh_core.ledger.adapters.daily_analysis import _strip_secret_fields


def test_strip_secret_fields_walks_tuples() -> None:
    cleaned = _strip_secret_fields(
        (
            {"score": 1, "api_key": "sk-test"},
            {"score": 2, "token": "tok", "ok": True},
        )
    )
    assert cleaned == ({"score": 1}, {"score": 2, "ok": True})
    assert isinstance(cleaned, tuple)


def test_strip_secret_fields_nested_tuple_inside_dict() -> None:
    cleaned = _strip_secret_fields({"details": ({"token": "x", "n": 1},)})
    assert cleaned == {"details": ({"n": 1},)}
