"""Parity tests for gesh_core.trading.contract (Phase 3.2).

The engine version is canonical, harmonized with product's stricter symbol cap.
These pin the full TradeIntent contract + adapters so neither consumer regresses:
  - manual() provenance: source= param (engine fix) defaults to "manual"
  - validate(): action/confidence/target/stop/take_profit/symbol rules
  - symbol cap: len > 12 (product's stricter rule, now shared)
  - from_consensus() verdict -> action/target mapping + scaling
"""
from __future__ import annotations

import pytest

from gesh_core.trading import contract
from gesh_core.trading.contract import TradeIntent, from_consensus, manual


def test_module_loads_from_gesh_core():
    assert "gesh_core" in (contract.__file__ or "")


# ─── manual() provenance (engine fix) ─────────────────────────────────────────

def test_manual_defaults_to_manual_source():
    intent = manual("nvda", "BUY", target_position_pct=0.02)
    assert intent.source == "manual"
    assert intent.symbol == "NVDA"          # upper-cased
    assert intent.action == "BUY"
    assert intent.confidence == 1.0


def test_manual_source_override_for_engine_signals():
    intent = manual("HOOD", "BUY", target_position_pct=0.02, source="market_scan")
    assert intent.source == "market_scan"   # provenance preserved (2026-06-14 fix)


def test_manual_passes_through_levels():
    intent = manual("AAPL", "SELL", target_position_pct=0.0,
                    stop_loss=180.0, take_profit=150.0, confidence=0.8)
    assert (intent.stop_loss, intent.take_profit, intent.confidence) == (180.0, 150.0, 0.8)


# ─── validate() ───────────────────────────────────────────────────────────────

def test_validate_clean_intent_has_no_problems():
    assert manual("NVDA", "BUY", target_position_pct=0.02).validate() == []


def test_validate_buy_requires_target_position_pct():
    problems = TradeIntent(symbol="NVDA", action="BUY", confidence=1.0, source="manual").validate()
    assert any("require target_position_pct" in p for p in problems)


@pytest.mark.parametrize("conf", [-0.1, 1.5])
def test_validate_confidence_bounds(conf):
    problems = manual("NVDA", "BUY", target_position_pct=0.02, confidence=conf).validate()
    assert any("confidence must be in [0,1]" in p for p in problems)


def test_validate_target_pct_bounds():
    problems = manual("NVDA", "BUY", target_position_pct=1.5).validate()
    assert any("target_position_pct must be in [0,1]" in p for p in problems)


def test_validate_nonpositive_levels():
    problems = TradeIntent(symbol="NVDA", action="BUY", confidence=1.0, source="m",
                           target_position_pct=0.02, stop_loss=-1.0, take_profit=0.0).validate()
    assert any("stop_loss must be > 0" in p for p in problems)
    assert any("take_profit must be > 0" in p for p in problems)


def test_validate_symbol_length_cap_shared():
    # product's stricter rule, now canonical for both repos
    long_symbol = "A" * 13
    problems = TradeIntent(symbol=long_symbol, action="HOLD", confidence=1.0, source="m").validate()
    assert any("symbol invalid" in p for p in problems)
    # exactly 12 is allowed
    assert TradeIntent(symbol="A" * 12, action="HOLD", confidence=1.0, source="m").validate() == []


def test_validate_non_ascii_symbol():
    problems = TradeIntent(symbol="NVDA™", action="HOLD", confidence=1.0, source="m").validate()
    assert any("symbol invalid" in p for p in problems)


# ─── from_consensus() ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("verdict,exp_action,exp_target", [
    ("STRONG BUY", "BUY", 0.02),
    ("BUY", "BUY", 0.01),          # 0.5 * cap
    ("SELL", "SELL", 0.0),
    ("STRONG SELL", "SELL", 0.0),
    ("HOLD", "HOLD", None),
    ("INSUFFICIENT DATA", "HOLD", None),
])
def test_from_consensus_verdict_mapping(verdict, exp_action, exp_target):
    row = {"symbol": "NVDA", "verdict": verdict, "raw_score": 0.6,
           "confidence": 80, "active_nodes": 8, "total_nodes": 11}
    intent = from_consensus(row, max_position_pct=0.02)
    assert intent.action == exp_action
    assert intent.target_position_pct == exp_target
    assert intent.source == "consensus"
    assert intent.confidence == pytest.approx(0.80)   # 80/100


def test_to_dict_roundtrip_keys():
    d = manual("NVDA", "BUY", target_position_pct=0.02).to_dict()
    for key in ("symbol", "action", "confidence", "source", "intent_uuid", "schema_version"):
        assert key in d
