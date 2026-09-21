"""R6 leftover: sibling allocation keys not in the original fail-closed matrix.

#79 parametrized stock/options caps, open positions, cash, and one pct.
max_open_contracts, scanner floors, and a single pct > 100 were untested.
"""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac
from gesh_core.trading.config import ConfigError


def _write_alloc(tmp_path, monkeypatch, **overrides) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg, allow_nan=True))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


@pytest.mark.parametrize(
    "key,value",
    [
        ("max_open_contracts", 0),
        ("max_open_contracts", -1),
        ("scanner_volume_min", -1),
        ("scanner_price_min", -0.5),
        ("scanner_price_max", -1.0),
        ("stock_allocation_pct", 101.0),
        ("options_allocation_pct", 150.0),
    ],
)
def test_leftover_allocation_numeric_fails_construction(
    tmp_path, monkeypatch, key: str, value: float
) -> None:
    overrides: dict[str, object] = {key: value}
    if key == "stock_allocation_pct":
        overrides["options_allocation_pct"] = 0.0
    elif key == "options_allocation_pct":
        overrides["stock_allocation_pct"] = 0.0
    _write_alloc(tmp_path, monkeypatch, **overrides)
    with pytest.raises(ConfigError) as exc:
        ac.load_config()
    assert key in str(exc.value)
