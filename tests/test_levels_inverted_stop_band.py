"""A swapped MIN/MAX stop band must still form a valid clamp.

``_atr_levels`` orders the pair so a misconfigured env (MIN > MAX) cannot
force every stop to the larger number. That would silently widen risk on
every ATR-backed paper entry.
"""

from __future__ import annotations

from gesh_core.trading import levels


def test_atr_levels_orders_inverted_min_max_band(monkeypatch) -> None:
    monkeypatch.setattr(levels, "EQUITY_MIN_STOP_PCT", 0.20)
    monkeypatch.setattr(levels, "EQUITY_MAX_STOP_PCT", 0.03)

    # 3×ATR = $6 on a $100 entry sits inside the ordered [3%, 20%] band.
    stop, target = levels._atr_levels("BUY", 100.0, 2.0)
    assert stop == 94.0
    assert target == 110.0


def test_atr_levels_inverted_band_still_caps_wide_atr(monkeypatch) -> None:
    monkeypatch.setattr(levels, "EQUITY_MIN_STOP_PCT", 0.20)
    monkeypatch.setattr(levels, "EQUITY_MAX_STOP_PCT", 0.03)

    # 3×ATR = $60 would exceed both ends of a swapped pair; the ordered hi is 20%.
    stop, target = levels._atr_levels("BUY", 100.0, 20.0)
    assert stop == 80.0
    assert target == 200.0
