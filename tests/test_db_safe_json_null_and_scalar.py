"""Non-object JSON in analysis columns degrades to {} without parse_error.

``_safe_json`` treats NULL/blank as an empty dict. Valid JSON that is not
an object (``null``, a number, a string) also becomes {} and is *not*
flagged. ``get_analysis_by_id`` must not 500, and must not claim a parse
error when the column was well-formed JSON of the wrong shape.
"""

from __future__ import annotations

from gesh_core import db


def test_safe_json_null_and_scalars_are_empty_dict_not_error() -> None:
    assert db._safe_json("null") == ({}, False)
    assert db._safe_json("42") == ({}, False)
    assert db._safe_json('"payload"') == ({}, False)
    assert db._safe_json("true") == ({}, False)
