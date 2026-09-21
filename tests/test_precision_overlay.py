"""Win-priority precision overlay — second-stage filter on consensus BUYs.

Primary model (11-node consensus) is recall-oriented: verdict BUY fires at
raw_score ≥ 0.25. Live engine book as of 2026-08-26: 25 closes, 24% win rate,
PF 0.82. López de Prado meta-labeling (AFML 2018) plus this engine's own
walk-forward IC table (docs/SIGNAL_PROFITABILITY_2026-06.md) say the cheap
lever is a precision filter on the highest-IC nodes, not a fitted model on
n=25 live trades.

Pure. No I/O. SELL/HOLD never blocked. Missing votes fail OPEN (score floor
still applies) so a market-scan row without a votes dict cannot halt the funnel.
"""
from __future__ import annotations

import pytest

from gesh_core.trading.autopilot_core import precision_overlay_blocks


def _row(*, verdict="BUY", votes=None, bullish=None, bearish=None):
    out = {"verdict": verdict, "votes": votes or {}}
    if bullish is not None:
        out["bullish"] = bullish
    if bearish is not None:
        out["bearish"] = bearish
    return out


def _agreeing_votes(**overrides):
    votes = {
        "Momentum": 1,
        "Trend": 1,
        "Rel.Strength": 1,
        "Volume": 1,
        "Macro": 1,
        "Fundamentals": 0,
        "Analyst": 0,
        "News": 0,
        "ECG": 0,
    }
    votes.update(overrides)
    return votes


# ── never blocks exits ────────────────────────────────────────────────────────

def test_sell_never_blocked():
    row = _row(verdict="SELL", votes=_agreeing_votes(**{"Rel.Strength": -1, "Momentum": -1}))
    d = precision_overlay_blocks("SELL", row)
    assert d.blocked is False
    assert d.reason == ""


def test_hold_never_blocked():
    d = precision_overlay_blocks("HOLD", _row(verdict="HOLD", votes={}))
    assert d.blocked is False


# ── missing votes fail open ───────────────────────────────────────────────────

def test_missing_votes_fail_open():
    d = precision_overlay_blocks("BUY", {"verdict": "BUY"})
    assert d.blocked is False
    assert d.reason == ""


def test_empty_votes_fail_open():
    d = precision_overlay_blocks("BUY", _row(votes={}))
    assert d.blocked is False


def test_disabled_via_env_fail_open(monkeypatch):
    monkeypatch.setenv("PRECISION_OVERLAY", "0")
    row = _row(votes=_agreeing_votes(**{"Rel.Strength": -1}))
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False


# ── Rel.Strength veto (highest IC node, +0.105) ───────────────────────────────

def test_rel_strength_bearish_blocks_buy():
    row = _row(votes=_agreeing_votes(**{"Rel.Strength": -1}), bullish=4, bearish=1)
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "Rel.Strength" in d.reason


def test_rel_strength_bearish_blocks_even_strong_buy():
    # A high weighted score with RS down vs SPY is the false-positive class.
    row = _row(
        verdict="STRONG BUY",
        votes=_agreeing_votes(**{"Rel.Strength": -1}),
        bullish=6,
        bearish=1,
    )
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "Rel.Strength" in d.reason


def test_rel_strength_abstain_does_not_veto():
    row = _row(
        votes=_agreeing_votes(**{"Rel.Strength": None}),
        bullish=4,
        bearish=0,
    )
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False


def test_rel_strength_bullish_passes():
    row = _row(votes=_agreeing_votes(), bullish=5, bearish=0)
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False
    assert d.reason == ""


# ── price-node confirmation (Trend or Momentum must be bullish) ───────────────

def test_both_price_nodes_not_bullish_blocks():
    row = _row(
        votes=_agreeing_votes(Momentum=0, Trend=-1),
        bullish=3,
        bearish=1,
    )
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "price confirm" in d.reason.lower() or "Momentum" in d.reason or "Trend" in d.reason


def test_trend_alone_is_enough_price_confirm():
    row = _row(
        votes=_agreeing_votes(Momentum=0, Trend=1),
        bullish=4,
        bearish=0,
    )
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False


def test_momentum_alone_is_enough_price_confirm():
    row = _row(
        votes=_agreeing_votes(Momentum=1, Trend=0),
        bullish=4,
        bearish=0,
    )
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False


def test_both_price_nodes_absent_fail_open_on_that_rule():
    votes = _agreeing_votes()
    votes.pop("Momentum")
    votes.pop("Trend")
    row = _row(votes=votes, bullish=4, bearish=0)
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False


# ── majority / net-vote floor ─────────────────────────────────────────────────

def test_more_bears_than_bulls_blocks():
    row = _row(votes=_agreeing_votes(), bullish=2, bearish=4)
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "majority" in d.reason.lower() or "net" in d.reason.lower()


def test_net_votes_below_two_blocks():
    # 3 bull, 2 bear → net 1 < 2
    row = _row(votes=_agreeing_votes(), bullish=3, bearish=2)
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True


def test_net_votes_of_two_passes():
    row = _row(votes=_agreeing_votes(), bullish=4, bearish=2)
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False


# ── Macro bearish veto (not STRONG BUY) ───────────────────────────────────────

def test_macro_bearish_blocks_plain_buy():
    row = _row(
        verdict="BUY",
        votes=_agreeing_votes(**{"Macro": -1}),
        bullish=4,
        bearish=1,
    )
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "Macro" in d.reason


def test_macro_bearish_allows_strong_buy_with_rel_strength():
    row = _row(
        verdict="STRONG BUY",
        votes=_agreeing_votes(**{"Macro": -1, "Rel.Strength": 1}),
        bullish=5,
        bearish=1,
    )
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is False


def test_macro_bearish_blocks_strong_buy_without_rel_strength():
    row = _row(
        verdict="STRONG BUY",
        votes=_agreeing_votes(**{"Macro": -1, "Rel.Strength": None}),
        bullish=5,
        bearish=1,
    )
    d = precision_overlay_blocks("BUY", row)
    assert d.blocked is True
    assert "Macro" in d.reason


# ── vote-count fallback when bullish/bearish keys missing ─────────────────────

def test_counts_votes_when_bullish_bearish_absent():
    votes = {
        "Momentum": 1,
        "Trend": 1,
        "Rel.Strength": 1,
        "Volume": 1,
        "Macro": 0,
        "Fundamentals": -1,
        "Analyst": 0,
        "News": 0,
        "ECG": 0,
    }
    # 4 bull, 1 bear, net 3 — pass
    d = precision_overlay_blocks("BUY", {"verdict": "BUY", "votes": votes})
    assert d.blocked is False


@pytest.mark.parametrize("flag", ["0", "false", "FALSE", "off"])
def test_env_off_values(monkeypatch, flag):
    monkeypatch.setenv("PRECISION_OVERLAY", flag)
    row = _row(votes=_agreeing_votes(**{"Rel.Strength": -1}))
    assert precision_overlay_blocks("BUY", row).blocked is False
