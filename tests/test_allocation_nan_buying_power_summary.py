"""NaN buying_power is truthy, so the summary uses it instead of falling through.

``bp = buying_power or stored or 0`` keeps NaN (unlike 0 / None). The report
header then ships NaN stock/options dollars — pin that so a later ``or 0``
rewrite cannot silently change the contract, and so callers know not to pass
a missing broker snapshot as NaN.
"""

from __future__ import annotations

import json
import math

import gesh_core.allocation_config as ac


def test_nan_buying_power_argument_poisons_usd_fields(tmp_path, monkeypatch) -> None:
    path = tmp_path / "gesh_config.json"
    stored = dict(ac.DEFAULT_CONFIG)
    stored["total_buying_power"] = 50_000.0
    path.write_text(json.dumps(stored))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    summary = ac.get_allocation_summary(float("nan"))
    assert math.isnan(summary["total_buying_power"])
    assert math.isnan(summary["stock_allocation_usd"])
    assert math.isnan(summary["options_allocation_usd"])
