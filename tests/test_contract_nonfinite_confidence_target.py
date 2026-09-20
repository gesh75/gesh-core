"""NaN/inf confidence and target fail closed via chained [0, 1] comparisons."""

from __future__ import annotations

import pytest

from gesh_core.trading.contract import TradeIntent


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_confidence_is_rejected(bad):
    """``0.0 <= nan <= 1.0`` is False — rewriting as ``x < 0 or x > 1`` would fail open."""
    problems = TradeIntent(
        symbol="NVDA",
        action="HOLD",
        confidence=bad,
        source="m",
    ).validate()
    assert any("confidence must be in [0,1]" in p for p in problems)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_target_is_rejected(bad):
    problems = TradeIntent(
        symbol="NVDA",
        action="BUY",
        confidence=1.0,
        source="m",
        target_position_pct=bad,
    ).validate()
    assert any("target_position_pct must be in [0,1]" in p for p in problems)
