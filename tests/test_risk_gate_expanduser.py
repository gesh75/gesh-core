"""Kill-switch ~ expansion and CASH_FLOOR math on a missing snapshot.

A HOME-relative KILL path is the documented default. Missing equity_summary
must not raise — live cash/equity collapse to 0; paper still uses simulated cash.
"""

from __future__ import annotations

from gesh_core.trading.config import RiskConfig
from gesh_core.trading.contract import manual
from gesh_core.trading.risk_gate_core import _kill_switch_present, _post_trade_cash_estimate


def test_kill_switch_expands_user_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    kill = tmp_path / ".gesh" / "KILL"
    kill.parent.mkdir()
    kill.write_text("")
    assert _kill_switch_present("~/.gesh/KILL") is True
    assert _kill_switch_present("~/.gesh/NOPE") is False


def test_live_missing_equity_summary_uses_zero_cash():
    cfg = RiskConfig(paper_mode=False, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    assert _post_trade_cash_estimate({}, intent, cfg) == 0.0


def test_paper_missing_equity_summary_still_uses_simulated_cash():
    cfg = RiskConfig(paper_mode=True, paper_cash_usd=100_000.0)
    intent = manual("NVDA", "BUY", target_position_pct=0.02)
    # equity=0 → no debit; paper cash is still the simulated 100k.
    assert _post_trade_cash_estimate({}, intent, cfg) == 100_000.0
