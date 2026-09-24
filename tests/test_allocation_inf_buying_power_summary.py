"""±Inf buying_power is truthy and flows into every dollar field.

Same ``or`` trap as NaN: inf is kept, -inf is kept. Zero already falls through
to stored buying power (leftover). Pin the inf path so a report header cannot
silently start treating inf as 'use stored'.
"""

from __future__ import annotations

import json
import math

import pytest

import gesh_core.allocation_config as ac


@pytest.mark.parametrize("buying_power", [float("inf"), float("-inf")])
def test_inf_buying_power_argument_stays_inf(tmp_path, monkeypatch, buying_power: float) -> None:
    path = tmp_path / "gesh_config.json"
    stored = dict(ac.DEFAULT_CONFIG)
    stored["total_buying_power"] = 50_000.0
    path.write_text(json.dumps(stored))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    summary = ac.get_allocation_summary(buying_power)
    assert math.isinf(summary["total_buying_power"])
    assert math.copysign(1.0, summary["total_buying_power"]) == math.copysign(1.0, buying_power)
    assert math.isinf(summary["stock_allocation_usd"])
