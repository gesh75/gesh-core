"""A missing or non-mapping scan row must fail open — never TypeError the funnel."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_missing_and_non_dict_rows_fail_open():
    assert precision_overlay_blocks("BUY").blocked is False
    for row in (None, {}, [], "", 0, "BUY"):
        d = precision_overlay_blocks("BUY", row)
        assert d.blocked is False, row
        assert d.reason == ""
