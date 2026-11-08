"""Call-time Kelly overlay knobs fall back on non-numeric env strings.

``inf`` / ``nan`` parse as IEEE and are claimed elsewhere. ``abc`` / blank
raise ``ValueError`` and must use the documented defaults — a launchd plist
that sets ``KELLY_MAX_GROSS_PCT=""`` must not crash the daily book.
"""

from __future__ import annotations

import pytest

from gesh_core import kelly


@pytest.mark.parametrize("raw", ["", "abc", "1.0x", "none"])
def test_garbage_gross_cap_uses_default(monkeypatch: pytest.MonkeyPatch, raw: str):
    monkeypatch.setenv("KELLY_MAX_GROSS_PCT", raw)
    assert kelly._max_gross_exposure() == pytest.approx(kelly._DEFAULT_MAX_GROSS_PCT)


@pytest.mark.parametrize("raw", ["", "abc", "70%"])
def test_garbage_corr_threshold_uses_default(monkeypatch: pytest.MonkeyPatch, raw: str):
    monkeypatch.setenv("KELLY_CORR_THRESHOLD", raw)
    assert kelly._corr_threshold() == pytest.approx(kelly._DEFAULT_CORR_THRESHOLD)


@pytest.mark.parametrize("raw", ["", "abc"])
def test_garbage_cost_bps_uses_default_drag(monkeypatch: pytest.MonkeyPatch, raw: str):
    monkeypatch.setenv("KELLY_COST_BPS", raw)
    monkeypatch.setenv("KELLY_REBALANCE_DAYS", raw)
    expected = (kelly._DEFAULT_COST_BPS / 10_000.0) / kelly._DEFAULT_REBALANCE_DAYS
    assert kelly._cost_drag_daily() == pytest.approx(expected)
