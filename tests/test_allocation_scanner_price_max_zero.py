"""``scanner_price_max=0`` disables the penny-universe ceiling.

The upper bound applies only when ``price_max > 0`` and the timeframe is in
``PRICE_CAPPED_MODES`` (``stock``). A hand-edited ``0`` or JSON ``null``
(coerced to falsy) therefore lets $450 names into a scanner meant for sub-$10
names. Intraday modes never apply the ceiling. Pin that so a later treat-0-as-
default cannot silently start blocking large-caps in ``stock`` mode.
"""
from __future__ import annotations

import json

import gesh_core.allocation_config as ac


def _write_cfg(tmp_path, monkeypatch, **overrides) -> None:
    cfg = dict(ac.DEFAULT_CONFIG)
    cfg["auto_trade"] = True
    cfg.update(overrides)
    path = tmp_path / "gesh_config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv("GESH_CONFIG_PATH", str(path))


def test_stock_mode_ceiling_blocks_above_max(tmp_path, monkeypatch) -> None:
    _write_cfg(tmp_path, monkeypatch, scanner_timeframe="stock", scanner_price_max=10)
    ok, reason = ac.validate_action(
        "BUY",
        "NVDA",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=450.0,
    )
    assert ok is False
    assert "above scanner maximum" in reason


def test_zero_price_max_disables_ceiling_in_stock_mode(tmp_path, monkeypatch) -> None:
    _write_cfg(tmp_path, monkeypatch, scanner_timeframe="stock", scanner_price_max=0)
    ok, reason = ac.validate_action(
        "BUY",
        "NVDA",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=450.0,
    )
    assert ok is True, reason


def test_intraday_mode_never_applies_ceiling(tmp_path, monkeypatch) -> None:
    _write_cfg(tmp_path, monkeypatch, scanner_timeframe="1HR", scanner_price_max=10)
    ok, reason = ac.validate_action(
        "BUY",
        "NVDA",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=450.0,
    )
    assert ok is True, reason
