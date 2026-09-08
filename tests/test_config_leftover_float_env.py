"""Leftover float knobs still use _env_float garbage→default, not fail-closed.

PAPER_CASH_USD / MIN_CONFIDENCE / MAX_SECTOR_PCT / MIN_CONFIDENCE_RISK_OFF
were not in the nonfinite-cap characterization. Garbage must fall back to
the ultra-conservative default so a typo cannot flip the CASH_FLOOR or
raise the confidence floor to NaN.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.config import load_risk_config


@pytest.mark.parametrize(
    ("key", "attr", "default"),
    [
        ("PAPER_CASH_USD", "paper_cash_usd", 100_000.0),
        ("MIN_CONFIDENCE", "min_confidence", 0.75),
        ("MAX_SECTOR_PCT", "max_sector_pct", 0.40),
        ("MIN_CONFIDENCE_RISK_OFF", "min_confidence_risk_off", 0.85),
    ],
)
@pytest.mark.parametrize("garbage", ["abc", "yes", "1.2.3", " "])
def test_leftover_float_garbage_falls_back_to_default(monkeypatch, key, attr, default, garbage):
    monkeypatch.setenv(key, garbage)
    cfg = load_risk_config()
    assert getattr(cfg, attr) == default


def test_leftover_float_valid_override_still_applies(monkeypatch):
    monkeypatch.setenv("PAPER_CASH_USD", "250000")
    monkeypatch.setenv("MIN_CONFIDENCE", "0.9")
    monkeypatch.setenv("MAX_SECTOR_PCT", "0.25")
    monkeypatch.setenv("MIN_CONFIDENCE_RISK_OFF", "0.95")
    cfg = load_risk_config()
    assert cfg.paper_cash_usd == 250_000.0
    assert cfg.min_confidence == 0.9
    assert cfg.max_sector_pct == 0.25
    assert cfg.min_confidence_risk_off == 0.95
