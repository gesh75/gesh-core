"""``update_config`` fails fast on unknown keys — it must not persist a typo
that later looks like a real gate (``auto_tradee=True``).

Load degrades unknown keys for forward-compat; the write path is program
code and must raise. Complements #58 (valid persist) without touching it.
"""
from __future__ import annotations

import pytest

import gesh_core.allocation_config as ac


def test_update_config_rejects_unknown_key(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_CONFIG_PATH", str(tmp_path / "gesh_config.json"))
    with pytest.raises(ValueError, match="Unknown config key"):
        ac.update_config(auto_tradee=True)
    # load_config may create a defaults file first; the typo must not persist.
    loaded = ac.load_config()
    assert "auto_tradee" not in loaded
    assert loaded["auto_trade"] is False


def test_update_config_rejects_unknown_key_among_valid_ones(tmp_path, monkeypatch):
    monkeypatch.setenv("GESH_CONFIG_PATH", str(tmp_path / "gesh_config.json"))
    with pytest.raises(ValueError, match="Unknown config key"):
        ac.update_config(max_stock_per_trade=8000.0, not_a_real_key=1)
