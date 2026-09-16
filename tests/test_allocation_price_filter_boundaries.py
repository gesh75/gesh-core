"""R1 leftover: scanner price comparisons are exclusive of the bound.

``current_price < min`` / ``> max`` — equality must stay OK. A zero print is
not ``None`` so the filter still runs (missing price skips; $0 does not).
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


def test_price_exactly_at_min_is_allowed(tmp_path, monkeypatch) -> None:
    _write_cfg(
        tmp_path,
        monkeypatch,
        auto_trade=True,
        scanner_timeframe="1HR",
        scanner_price_min=0.10,
    )
    result = ac.validate_action(
        "BUY",
        "EDGE",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=0.10,
    )
    assert result.ok is True
    assert result.code == "OK"


def test_zero_price_is_filtered_not_treated_as_missing(tmp_path, monkeypatch) -> None:
    _write_cfg(
        tmp_path,
        monkeypatch,
        auto_trade=True,
        scanner_timeframe="1HR",
        scanner_price_min=0.10,
    )
    missing = ac.validate_action(
        "BUY",
        "EDGE",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=None,
    )
    assert missing.ok is True
    assert missing.code == "OK"

    zero = ac.validate_action(
        "BUY",
        "EDGE",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=0.0,
    )
    assert zero.ok is False
    assert zero.code == "PRICE_FILTER"


def test_stock_ceiling_is_exclusive_of_max(tmp_path, monkeypatch) -> None:
    _write_cfg(
        tmp_path,
        monkeypatch,
        auto_trade=True,
        scanner_timeframe="stock",
        scanner_price_min=0.10,
        scanner_price_max=10.00,
    )
    at_max = ac.validate_action(
        "BUY",
        "PENNY",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=10.00,
    )
    assert at_max.ok is True
    assert at_max.code == "OK"

    over = ac.validate_action(
        "BUY",
        "PENNY",
        100.0,
        open_positions=0,
        current_cash=100_000,
        current_price=10.01,
    )
    assert over.ok is False
    assert over.code == "PRICE_FILTER"
    assert "above scanner maximum" in over.reason
