"""R6 leftover: update_config is the write boundary and must fail closed.

load_config rejects invalid file numerics. The programmatic write path
(_validate_allocation_numeric + relationships) was not pinned.
"""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac
from gesh_core.trading.config import ConfigError


def _seed(tmp_path, monkeypatch) -> None:
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(dict(ac.DEFAULT_CONFIG)))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_update_config_rejects_nonfinite_cap(tmp_path, monkeypatch) -> None:
    _seed(tmp_path, monkeypatch)
    with pytest.raises(ConfigError) as exc:
        ac.update_config(max_stock_per_trade=float("inf"))
    assert "max_stock_per_trade" in str(exc.value)


def test_update_config_rejects_negative_buffer(tmp_path, monkeypatch) -> None:
    _seed(tmp_path, monkeypatch)
    with pytest.raises(ConfigError) as exc:
        ac.update_config(min_cash_buffer=-1.0)
    assert "min_cash_buffer" in str(exc.value)


def test_update_config_rejects_pct_above_hundred(tmp_path, monkeypatch) -> None:
    _seed(tmp_path, monkeypatch)
    with pytest.raises(ConfigError) as exc:
        ac.update_config(stock_allocation_pct=101.0, options_allocation_pct=0.0)
    assert "stock_allocation_pct" in str(exc.value)
    assert "maximum" in str(exc.value)


def test_update_config_rejects_pct_pair_that_no_longer_sums(tmp_path, monkeypatch) -> None:
    _seed(tmp_path, monkeypatch)
    with pytest.raises(ConfigError) as exc:
        ac.update_config(stock_allocation_pct=80.0)
    msg = str(exc.value)
    assert "stock_allocation_pct" in msg or "options_allocation_pct" in msg


def test_update_config_accepts_balanced_pct_pair(tmp_path, monkeypatch) -> None:
    _seed(tmp_path, monkeypatch)
    out = ac.update_config(stock_allocation_pct=60.0, options_allocation_pct=40.0)
    assert out["stock_allocation_pct"] == 60.0
    assert out["options_allocation_pct"] == 40.0
