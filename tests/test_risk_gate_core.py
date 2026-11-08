"""Parity tests for gesh_core.trading.risk_gate_core (Phase 3.5).

Only the seam-free shared primitives live here. The CASH_FLOOR math is
safety-critical (rule #32): PAPER must size against the simulated cfg.paper_cash_usd,
LIVE against the real account cash.
"""
from __future__ import annotations

import math

import pytest

from gesh_core.trading import risk_gate_core as rgc
from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import (
    GateVerdict,
    _kill_switch_present,
    _post_trade_cash_estimate,
)


def test_module_loads_from_gesh_core():
    assert "gesh_core" in (rgc.__file__ or "")


# ─── GateVerdict ──────────────────────────────────────────────────────────────

def test_gate_verdict_to_dict():
    v = GateVerdict(approved=True, reason=None, gates={"KILL_SWITCH": True},
                    intent_id=1, decision_id=2)
    d = v.to_dict()
    assert d["approved"] is True and d["gates"]["KILL_SWITCH"] is True
    assert d["intent_id"] == 1 and d["decision_id"] == 2


# ─── kill switch ──────────────────────────────────────────────────────────────

def test_kill_switch_absent(tmp_path):
    assert _kill_switch_present(str(tmp_path / "nope")) is False


def test_kill_switch_present(tmp_path):
    f = tmp_path / "KILL"
    f.write_text("")
    assert _kill_switch_present(str(f)) is True


# ─── CASH_FLOOR math (rule #32) ───────────────────────────────────────────────

def _pf(cash, equity):
    return {"equity_summary": {"cash": cash, "portfolio_equity": equity}}


def test_paper_uses_simulated_cash_not_real():
    cfg = RiskConfig(paper_mode=True, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    # Real account near-empty ($300) must NOT starve a paper BUY.
    post = _post_trade_cash_estimate(_pf(cash=300.0, equity=50_000.0), intent, cfg)
    # 100_000 - 0.02*50_000 = 99_000  (uses simulated cash, ignores the $300)
    assert post == pytest.approx(99_000.0)


def test_live_uses_real_cash():
    cfg = RiskConfig(paper_mode=False, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    post = _post_trade_cash_estimate(_pf(cash=10_000.0, equity=50_000.0), intent, cfg)
    # 10_000 - 0.02*50_000 = 9_000  (real cash, paper_cash_usd ignored)
    assert post == pytest.approx(9_000.0)


def test_sell_returns_cash_unchanged():
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "SELL", target_position_pct=0.0)
    assert _post_trade_cash_estimate(_pf(cash=7_777.0, equity=50_000.0), intent, cfg) == pytest.approx(7_777.0)


def test_live_null_cash_is_zero_not_typeerror():
    """Key-present null used to be fine (`or 0`); keep that, and stay finite."""
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    post = _post_trade_cash_estimate(_pf(cash=None, equity=50_000.0), intent, cfg)
    assert post == pytest.approx(-1_000.0)


@pytest.mark.parametrize("bad_cash", [float("nan"), float("inf"), "N/A", "", {"usd": 10}])
def test_live_unusable_cash_does_not_crash_or_nan_the_floor(bad_cash):
    """CASH_FLOOR is shared by the whole book. Junk cash must not TypeError a
    sibling SELL, and NaN must not leak out — ``nan < min_cash`` is False, so
    the host would fail open and let a LIVE BUY through."""
    cfg = RiskConfig(paper_mode=False)
    buy = manual("NVDA", "BUY", target_position_pct=0.02)
    sell = manual("AMD", "SELL", target_position_pct=0.0)
    buy_post = _post_trade_cash_estimate(_pf(cash=bad_cash, equity=50_000.0), buy, cfg)
    sell_post = _post_trade_cash_estimate(_pf(cash=bad_cash, equity=50_000.0), sell, cfg)
    assert math.isfinite(buy_post)
    assert math.isfinite(sell_post)
    # Unknown LIVE cash on a BUY → fail closed (0 < default $500 buffer).
    assert buy_post == 0.0
    assert sell_post == 0.0


@pytest.mark.parametrize("bad_equity", [float("nan"), float("inf"), "n/a", None])
def test_live_unusable_equity_fails_closed_on_buy(bad_equity):
    """Treating NaN equity as 0 makes target_pct × equity = 0, so the BUY
    looks free and CASH_FLOOR passes. Refuse the estimate instead."""
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    post = _post_trade_cash_estimate(_pf(cash=10_000.0, equity=bad_equity), intent, cfg)
    assert math.isfinite(post)
    assert post == 0.0


def test_missing_equity_summary_does_not_crash_sell():
    """A failed snapshot that sets equity_summary=None used to AttributeError
    before any per-action branch — aborting stop-sweep exits."""
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "SELL", target_position_pct=0.0)
    post = _post_trade_cash_estimate({"equity_summary": None}, intent, cfg)
    assert post == 0.0


def test_nan_target_pct_buy_fails_closed():
    cfg = RiskConfig(paper_mode=False)
    intent = manual("NVDA", "BUY", target_position_pct=float("nan"))
    post = _post_trade_cash_estimate(_pf(cash=10_000.0, equity=50_000.0), intent, cfg)
    assert post == 0.0
