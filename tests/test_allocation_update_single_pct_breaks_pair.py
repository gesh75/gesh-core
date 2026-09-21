"""R6 leftover: updating one allocation pct still re-checks the pair.

#82 pins update_config when both percents are passed together. A caller that
only raises stock_allocation_pct (leaving the loaded options pct) must still
fail closed — otherwise the book can be configured to allocate 110% of BP.
"""

from __future__ import annotations

import json

import pytest

import gesh_core.allocation_config as ac
from gesh_core.trading.config import ConfigError


def test_update_single_pct_that_breaks_the_pair_raises(tmp_path, monkeypatch) -> None:
    path = tmp_path / "gesh_config.json"
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["stock_allocation_pct"] = 70.0
    cfg["options_allocation_pct"] = 30.0
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))

    with pytest.raises(ConfigError, match="must sum to 100"):
        ac.update_config(stock_allocation_pct=80.0)

    loaded = ac.load_config()
    assert loaded["stock_allocation_pct"] == 70.0
    assert loaded["options_allocation_pct"] == 30.0
