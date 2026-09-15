"""R1 leftover: price checks still run when live permission is OFF.

#77 pinned size, position, and cash before auto_trade. CHANGELOG also
promises the scanner price filter. Daily mode skips that filter (#76);
1HR does not — a cheap print must not become LIVE_PERMISSION or OK.
"""

from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def _write_cfg(tmp_path, monkeypatch, **overrides) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_validate_action_price_filter_beats_live_permission(tmp_path, monkeypatch) -> None:
    _write_cfg(
        tmp_path,
        monkeypatch,
        auto_trade=False,
        scanner_timeframe="1HR",
        scanner_price_min=0.10,
    )
    result = ac.validate_action(
        "BUY",
        "PENNY",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=0.05,
    )
    assert result.ok is False
    assert result.code == "PRICE_FILTER"
    assert "Auto-trade" not in result.reason
    assert "below scanner minimum" in result.reason


def test_validate_action_price_filter_still_runs_without_live_permission(
    tmp_path, monkeypatch
) -> None:
    _write_cfg(
        tmp_path,
        monkeypatch,
        auto_trade=False,
        scanner_timeframe="1HR",
        scanner_price_min=0.10,
    )
    result = ac.validate_action(
        "BUY",
        "PENNY",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=0.05,
        require_live_permission=False,
    )
    assert result.ok is False
    assert result.code == "PRICE_FILTER"
