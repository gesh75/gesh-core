"""Live CASH_FLOOR math uses negative snapshot cash as-is.

``_post_trade_cash_estimate`` does not clamp cash. A margin/negative-cash
snapshot therefore produces a more-negative post-trade estimate on BUY and
leaves SELL unchanged. Paper still ignores the real cash. Pin the current
arithmetic so a later clamp cannot silently change who the floor blocks.
"""

from __future__ import annotations

import pytest

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _post_trade_cash_estimate


def _pf(cash, equity):
    return {"equity_summary": {"cash": cash, "portfolio_equity": equity}}


def test_live_negative_cash_is_used_as_is() -> None:
    cfg = RiskConfig(paper_mode=False, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    post = _post_trade_cash_estimate(_pf(cash=-1_000.0, equity=50_000.0), intent, cfg)
    # -1000 - 0.02 * 50000 = -2000
    assert post == pytest.approx(-2_000.0)


def test_live_sell_leaves_negative_cash_unchanged() -> None:
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "SELL", target_position_pct=0.0)
    post = _post_trade_cash_estimate(_pf(cash=-1_000.0, equity=50_000.0), intent, cfg)
    assert post == pytest.approx(-1_000.0)


def test_paper_still_ignores_negative_real_cash() -> None:
    cfg = RiskConfig(paper_mode=True, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    post = _post_trade_cash_estimate(_pf(cash=-1_000.0, equity=50_000.0), intent, cfg)
    assert post == pytest.approx(99_000.0)


def test_live_string_cash_still_parses() -> None:
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    post = _post_trade_cash_estimate(_pf(cash="10000", equity=50_000.0), intent, cfg)
    assert post == pytest.approx(9_000.0)
