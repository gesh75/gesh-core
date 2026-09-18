"""A JSON null numeric cap must fail construction, not restore the default.

Hand-edited ``"max_stock_per_trade": null`` used to look like a missing key
and silently reopen the $5,000 default. Fail-closed keeps the corrupt file
from authorizing oversized live trades.
"""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac
from gesh_core.trading.config import ConfigError


def _write(tmp_path, monkeypatch, **overrides) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


@pytest.mark.parametrize(
    "key",
    [
        "max_stock_per_trade",
        "max_options_per_trade",
        "min_cash_buffer",
        "max_open_positions",
    ],
)
def test_null_numeric_allocation_key_fails_construction(tmp_path, monkeypatch, key: str) -> None:
    _write(tmp_path, monkeypatch, **{key: None})
    with pytest.raises(ConfigError) as exc:
        ac.load_config()
    assert key in str(exc.value)
