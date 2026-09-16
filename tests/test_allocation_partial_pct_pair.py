"""R6 leftover: a partial allocation pair still has to sum to 100.

load_config merges stored keys onto DEFAULT_CONFIG. Editing only
``stock_allocation_pct`` leaves options at the 30% default — 80+30 must
fail construction rather than silently over-allocate.
"""

from __future__ import annotations

import json

import pytest

from gesh_core import allocation_config as ac
from gesh_core.trading.config import ConfigError


def test_stored_stock_pct_alone_fails_against_default_options(tmp_path, monkeypatch) -> None:
    # Hand-edited file omits options — merge keeps the 30% default.
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps({"stock_allocation_pct": 80.0}))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    with pytest.raises(ConfigError) as exc:
        ac.load_config()
    msg = str(exc.value)
    assert "stock_allocation_pct" in msg or "options_allocation_pct" in msg


def test_stored_options_pct_alone_fails_against_default_stock(tmp_path, monkeypatch) -> None:
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps({"options_allocation_pct": 50.0}))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    with pytest.raises(ConfigError) as exc:
        ac.load_config()
    msg = str(exc.value)
    assert "stock_allocation_pct" in msg or "options_allocation_pct" in msg


def test_balanced_override_pair_loads(tmp_path, monkeypatch) -> None:
    path = tmp_path / "gesh_config.json"
    path.write_text(
        json.dumps({"stock_allocation_pct": 80.0, "options_allocation_pct": 20.0})
    )
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    loaded = ac.load_config()
    assert loaded["stock_allocation_pct"] == 80.0
    assert loaded["options_allocation_pct"] == 20.0
