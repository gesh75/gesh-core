"""Parity tests for gesh_core.trading.risk_gate_core (Phase 3.5).

Only the seam-free shared primitives live here. The CASH_FLOOR math is
safety-critical (rule #32): PAPER must size against the simulated cfg.paper_cash_usd,
LIVE against the real account cash.
"""
from __future__ import annotations

import pytest

from gesh_core.trading import risk_gate_core as rgc
from gesh_core.trading.risk_gate_core import GateVerdict, _kill_switch_present, _post_trade_cash_estimate
from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual


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
