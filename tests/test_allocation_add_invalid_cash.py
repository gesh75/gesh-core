"""ADD uses the same cash gate as BUY — poisoned cash must fail closed."""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def _enable_auto_trade(tmp_path, monkeypatch) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_add_rejects_nonfinite_and_non_numeric_cash(tmp_path, monkeypatch):
    """NaN > buffer is False in IEEE-754 — ADD must not skip the cash floor."""
    _enable_auto_trade(tmp_path, monkeypatch)

    for cash in (float("nan"), float("inf"), float("-inf"), True, "10000"):
        result = ac.validate_action(
            "ADD", "NVDA", 100.0, open_positions=0, current_cash=cash
        )
        assert result.ok is False, cash
        assert "Invalid cash" in result.reason
        assert result.code == "INVALID_CASH"
