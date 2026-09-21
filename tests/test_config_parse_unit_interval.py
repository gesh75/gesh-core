"""R6 leftover: parse_unit_interval is the Kelly cap seam.

Unknown keys use inclusive [0, 1] + allow_zero. Known Kelly specs keep
their own zero/max rules. Invalid tokens must raise without echoing raw
input — the same fail-closed contract as load_risk_config.
"""

from __future__ import annotations

import pytest

from gesh_core import kelly
from gesh_core.trading.config import ConfigError, parse_unit_interval


def test_missing_and_blank_keep_default() -> None:
    assert parse_unit_interval("CUSTOM_CAP", None, 0.25) == 0.25
    assert parse_unit_interval("CUSTOM_CAP", "", 0.25) == 0.25
    assert parse_unit_interval("CUSTOM_CAP", "   ", 0.25) == 0.25


def test_unknown_key_accepts_zero_and_one() -> None:
    assert parse_unit_interval("CUSTOM_CAP", "0", 0.25) == 0.0
    assert parse_unit_interval("CUSTOM_CAP", "1", 0.25) == 1.0
    assert parse_unit_interval("CUSTOM_CAP", "0.18", 0.25) == pytest.approx(0.18)


@pytest.mark.parametrize("raw", ["-0.1", "1.1", "inf", "nan", "abc", "100"])
def test_unknown_key_rejects_out_of_range_without_echoing(raw) -> None:
    with pytest.raises(ConfigError) as exc:
        parse_unit_interval("CUSTOM_CAP", raw, 0.25)
    msg = str(exc.value)
    assert "CUSTOM_CAP" in msg
    if any(c.isalpha() for c in raw):
        assert raw not in msg


def test_kelly_gross_zero_is_a_valid_unit_interval(monkeypatch) -> None:
    monkeypatch.setenv("KELLY_MAX_GROSS_PCT", "0")
    assert parse_unit_interval("KELLY_MAX_GROSS_PCT", "0", 1.0) == 0.0
    assert kelly._max_gross_exposure() == 0.0
