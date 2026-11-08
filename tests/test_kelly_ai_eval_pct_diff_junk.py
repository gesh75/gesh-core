"""Kelly AI pct_diff must degrade on missing/empty and not invent a penalty.

``float(ai_eval.get("pct_diff", 0) or 0)`` treats missing/None/"" as 0 (no
overvaluation haircut). Junk that is not float-coercible currently raises —
pin that so a silent swallow that changes live size is a reviewed change,
not an invisible dashboard crash fix.
"""
from __future__ import annotations

import numpy as np
import pytest

from gesh_core.kelly import kelly_size_holding

_POSITIVE_DRIFT = np.random.default_rng(42).normal(0.002, 0.01, 120).astype(float)


def _size(**kwargs: object) -> dict:
    return kelly_size_holding(
        "X",
        1_000,
        100_000,
        10,
        12,
        returns=_POSITIVE_DRIFT,
        **kwargs,
    )


def test_missing_or_empty_pct_diff_does_not_penalize():
    base = _size()
    missing = _size(ai_eval={"verdict": "BUY"})
    none = _size(ai_eval={"verdict": "BUY", "pct_diff": None})
    empty = _size(ai_eval={"verdict": "BUY", "pct_diff": ""})
    empty_map = _size(ai_eval={"verdict": "BUY", "pct_diff": {}})

    assert missing["ai_penalty"] == 1.0
    assert none["ai_penalty"] == 1.0
    assert empty["ai_penalty"] == 1.0
    assert empty_map["ai_penalty"] == 1.0
    assert missing["optimal_pct"] == base["optimal_pct"]
    assert none["optimal_pct"] == base["optimal_pct"]
    assert empty["optimal_pct"] == base["optimal_pct"]
    assert empty_map["optimal_pct"] == base["optimal_pct"]


@pytest.mark.parametrize("junk", ["N/A", {"x": 1}, ["-20"]])
def test_non_numeric_pct_diff_raises(junk):
    with pytest.raises((TypeError, ValueError)):
        _size(ai_eval={"verdict": "BUY", "pct_diff": junk})
