"""votes must be a non-empty dict — list/scalar/bool shapes fail open."""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_non_dict_votes_fail_open():
    for votes in (None, [], ["Rel.Strength", -1], "Rel.Strength=-1", 1, True):
        d = precision_overlay_blocks("BUY", {"verdict": "BUY", "votes": votes})
        assert d.blocked is False, votes
        assert d.reason == ""
