"""When tallies are absent, ``v == 1`` treats JSON true as a bullish vote.

Four True nodes and no bearish -1 is net 4, so the entry is admitted. A later
``isinstance(v, int)`` change would drop those votes to net 0 and start
blocking every bool-valued scan row.
"""

from __future__ import annotations

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def test_true_vote_values_count_as_bullish_when_tallies_missing() -> None:
    d = precision_overlay_blocks(
        "BUY",
        {
            "verdict": "BUY",
            "votes": {
                "Momentum": True,
                "Trend": True,
                "Rel.Strength": True,
                "Volume": True,
                "Macro": 0,
            },
        },
    )
    assert d.blocked is False
    assert d.reason == ""
