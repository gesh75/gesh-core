"""Parity tests for gesh_core.trading.contract (Phase 3.2).

The engine version is canonical, harmonized with product's stricter symbol cap.
These pin the full TradeIntent contract + adapters so neither consumer regresses:
  - manual() provenance: manual callers cannot claim an engine source
  - validate(): action/confidence/target/stop/take_profit/symbol rules
  - symbol cap: len > 12 (product's stricter rule, now shared)
  - from_consensus() verdict -> action/target mapping + scaling
"""

from __future__ import annotations

import math

import pytest

from gesh_core.trading import contract
from gesh_core.trading.contract import TradeIntent, from_consensus, manual


def test_module_loads_from_gesh_core():
    assert "gesh_core" in (contract.__file__ or "")


# ─── manual() provenance ──────────────────────────────────────────────────────


def test_manual_defaults_to_manual_source():
    intent = manual("nvda", "BUY", target_position_pct=0.02)
    assert intent.source == "manual"
    assert intent.symbol == "NVDA"  # upper-cased
    assert intent.action == "BUY"
    assert intent.confidence == 1.0


def test_manual_rejects_engine_source_spoofing():
    with pytest.raises(ValueError, match="must use source='manual'"):
        manual("HOOD", "BUY", target_position_pct=0.02, source="market_scan")  # type: ignore[arg-type]


def test_manual_accepts_explicit_manual_source_for_compatibility():
    intent = manual("HOOD", "BUY", target_position_pct=0.02, source="manual")
    assert intent.source == "manual"


def test_manual_passes_through_levels():
    intent = manual(
        "AAPL", "SELL", target_position_pct=0.0, stop_loss=180.0, take_profit=150.0, confidence=0.8
    )
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
    problems = TradeIntent(
        symbol="NVDA",
        action="BUY",
        confidence=1.0,
        source="m",
        target_position_pct=0.02,
        stop_loss=-1.0,
        take_profit=0.0,
    ).validate()
    assert any("stop_loss must be > 0" in p for p in problems)
    assert any("take_profit must be > 0" in p for p in problems)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_validate_nonfinite_levels(bad):
    """NaN/inf stops must fail closed — ``NaN <= 0`` is False in IEEE-754."""
    problems = TradeIntent(
        symbol="NVDA",
        action="BUY",
        confidence=1.0,
        source="m",
        target_position_pct=0.02,
        stop_loss=bad,
        take_profit=bad,
    ).validate()
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


@pytest.mark.parametrize(
    "verdict,exp_action,exp_target",
    [
        ("STRONG BUY", "BUY", 0.02),
        ("BUY", "BUY", 0.01),  # 0.5 * cap
        ("SELL", "SELL", 0.0),
        ("STRONG SELL", "SELL", 0.0),
        ("HOLD", "HOLD", None),
        ("INSUFFICIENT DATA", "HOLD", None),
    ],
)
def test_from_consensus_verdict_mapping(verdict, exp_action, exp_target):
    row = {
        "symbol": "NVDA",
        "verdict": verdict,
        "raw_score": 0.6,
        "confidence": 80,
        "active_nodes": 8,
        "total_nodes": 11,
    }
    intent = from_consensus(row, max_position_pct=0.02)
    assert intent.action == exp_action
    assert intent.target_position_pct == exp_target
    assert intent.source == "consensus"
    assert intent.confidence == pytest.approx(0.80)  # 80/100


def test_to_dict_roundtrip_keys():
    d = manual("NVDA", "BUY", target_position_pct=0.02).to_dict()
    for key in ("symbol", "action", "confidence", "source", "intent_uuid", "schema_version"):
        assert key in d


def test_provenance_roundtrips_without_invented_defaults():
    intent = manual("NVDA", "BUY", target_position_pct=0.02)

    assert {
        key: intent.to_dict()[key]
        for key in (
            "purpose",
            "canonical_key",
            "run_id",
            "strategy_version",
            "quote_provider",
            "quote_as_of",
        )
    } == {
        "purpose": None,
        "canonical_key": None,
        "run_id": None,
        "strategy_version": None,
        "quote_provider": None,
        "quote_as_of": None,
    }


@pytest.mark.parametrize("adapter", ["manual", "consensus"])
def test_adapters_accept_explicit_provenance(adapter):
    provenance = {
        "purpose": "ENTRY",
        "canonical_key": "run-42:NVDA:BUY",
        "run_id": "run-42",
        "strategy_version": "strategy-v3",
        "quote_provider": "fixture-provider",
        "quote_as_of": "2026-08-04T12:34:56+00:00",
    }
    if adapter == "manual":
        intent = manual(
            "NVDA",
            "BUY",
            target_position_pct=0.02,
            **provenance,
        )
    else:
        intent = from_consensus(
            {
                "symbol": "NVDA",
                "verdict": "BUY",
                "raw_score": 0.6,
                "confidence": 80,
                "active_nodes": 8,
                "total_nodes": 11,
            },
            **provenance,
        )

    assert {key: getattr(intent, key) for key in provenance} == provenance


# ─── confidence semantics (audit PR4 — resolved as division of labor) ────────


@pytest.mark.parametrize(
    "raw_score,confidence",
    [
        (None, 80),
        (0.6, None),
        (None, None),
        (float("nan"), 80),
        (0.6, float("nan")),
        (float("inf"), 80),
        ("", ""),
        ("not-a-number", "also-bad"),
    ],
)
def test_from_consensus_null_or_nonfinite_scores_fail_closed(raw_score, confidence):
    """A single INSUFFICIENT/null-score row must not TypeError the adapter.

    Callers map from_consensus across the book; one null raw_score used to
    abort every sibling symbol, including SELLs. Unusable scores become 0
    so the P2 entry floor and min_confidence reject the BUY instead.
    """
    intent = from_consensus(
        {
            "symbol": "NVDA",
            "verdict": "INSUFFICIENT DATA",
            "raw_score": raw_score,
            "confidence": confidence,
            "active_nodes": 0,
            "total_nodes": 11,
        }
    )
    assert intent.action == "HOLD"
    assert intent.target_position_pct is None
    assert math.isfinite(intent.confidence)
    assert 0.0 <= intent.confidence <= 1.0


def test_from_consensus_null_row_does_not_abort_sibling_sell():
    """Callers map from_consensus across the book; one null must not raise."""
    book = [
        {
            "symbol": "AMD",
            "verdict": "INSUFFICIENT DATA",
            "raw_score": None,
            "confidence": None,
            "active_nodes": 0,
            "total_nodes": 11,
        },
        {
            "symbol": "NVDA",
            "verdict": "SELL",
            "raw_score": -0.90,
            "confidence": 80,
            "active_nodes": 8,
            "total_nodes": 11,
        },
    ]
    intents = [from_consensus(row) for row in book]
    assert [intent.action for intent in intents] == ["HOLD", "SELL"]
    assert intents[1].target_position_pct == 0.0


def test_from_consensus_null_raw_score_on_sell_still_closes():
    """The production failure: one null-score row must not abort a SELL."""
    intent = from_consensus(
        {
            "symbol": "NVDA",
            "verdict": "SELL",
            "raw_score": None,
            "confidence": None,
            "active_nodes": 0,
            "total_nodes": 11,
        }
    )
    assert intent.action == "SELL"
    assert intent.target_position_pct == 0.0
    assert intent.confidence == 0.0


def test_from_consensus_preserves_negative_raw_score_in_rationale():
    intent = from_consensus(
        {
            "symbol": "NVDA",
            "verdict": "SELL",
            "raw_score": -0.90,
            "confidence": 80,
            "active_nodes": 8,
            "total_nodes": 11,
        }
    )
    assert intent.action == "SELL"
    assert "raw_score=-0.90" in (intent.rationale or "")


def test_from_consensus_null_raw_score_on_buy_is_zero_conviction():
    intent = from_consensus(
        {
            "symbol": "NVDA",
            "verdict": "BUY",
            "raw_score": None,
            "confidence": 100,
            "active_nodes": 11,
            "total_nodes": 11,
        }
    )
    assert intent.action == "BUY"
    assert intent.confidence == pytest.approx(1.0)
    # Rationale must still render — the old float(None) crashed before this.
    assert "raw_score=+0.00" in (intent.rationale or "")


def test_from_consensus_confidence_is_participation_not_conviction():
    """confidence stays 0..1 participation (data coverage). Conviction is
    gated separately by the P2 entry floor on raw_score
    (RiskConfig.min_entry_score) — blending raw_score in here double-gated
    entries and silently re-calibrated every consumer's min_confidence."""
    base = {
        "symbol": "NVDA",
        "verdict": "BUY",
        "confidence": 80,
        "active_nodes": 8,
        "total_nodes": 11,
    }
    weak = from_consensus({**base, "raw_score": 0.26})
    strong = from_consensus({**base, "raw_score": 0.60})
    assert weak.confidence == pytest.approx(0.80)
    assert strong.confidence == pytest.approx(0.80)
