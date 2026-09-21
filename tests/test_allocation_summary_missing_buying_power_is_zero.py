"""Omitted buying_power and unset stored total must summarize as $0.

#85 pins "omitted arg uses stored total". The inverse — no arg and
``total_buying_power is None`` — must not invent a notional book. Report
headers that assume a leftover $100k would mis-size the allocation split.
"""

from __future__ import annotations

import json
from pathlib import Path

import gesh_core.allocation_config as ac


def test_summary_with_no_arg_and_no_stored_total_is_zero(
    tmp_path: Path, monkeypatch
) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    summary = ac.get_allocation_summary()
    assert summary["total_buying_power"] == 0
    assert summary["stock_allocation_usd"] == 0
    assert summary["options_allocation_usd"] == 0
    assert summary["remaining_usd"] == 0
