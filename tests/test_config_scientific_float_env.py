"""Scientific-notation floats are accepted by ``_env_float``.

Launchd and some .env generators emit ``1e-2`` rather than ``0.01``.
``float()`` parses that; a later "must look like a decimal" check would
silently restore the 2% position cap and change live sizing.
"""

from __future__ import annotations

from gesh_core.trading.config import load_risk_config


def test_scientific_notation_position_and_loss_caps(monkeypatch):
    monkeypatch.setenv("MAX_POSITION_PCT", "1e-2")
    monkeypatch.setenv("MAX_DAILY_LOSS_PCT", "5e-3")
    monkeypatch.setenv("MIN_CASH_BUFFER_USD", "5e2")
    cfg = load_risk_config()
    assert cfg.max_position_pct == 0.01
    assert cfg.max_daily_loss_pct == 0.005
    assert cfg.min_cash_buffer_usd == 500.0
