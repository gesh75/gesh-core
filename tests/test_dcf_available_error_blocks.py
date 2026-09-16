"""DCF leftover: ``available`` is fail-closed on error / missing / short history.

#76 pins length-mismatch / missing-series. A complete-looking tuple with
``error`` set, a ``missing`` tag, or fewer than MIN_PERIODS years must still
be unusable — callers check ``.available`` before building a valuation.
"""

from __future__ import annotations

from gesh_core.dcf.inputs import MIN_PERIODS, DCFInputs


def _complete(**overrides) -> DCFInputs:
    years = (2023, 2024, 2025)
    series = (100.0, 110.0, 120.0)
    kwargs = dict(
        symbol="AMD",
        years=years,
        revenue=series,
        ebitda=series,
        capex=series,
        nwc=series,
        tax_rate=0.21,
        shares_outstanding=1.6,
        net_debt=-2.0,
    )
    kwargs.update(overrides)
    return DCFInputs(**kwargs)


def test_complete_inputs_are_available() -> None:
    assert _complete().available is True


def test_error_blocks_available_even_with_complete_series() -> None:
    assert _complete(error="empty statements").available is False


def test_missing_tag_blocks_available() -> None:
    assert _complete(missing=("tax_rate",)).available is False


def test_short_history_blocks_available() -> None:
    short = (2024, 2025)
    pair = (100.0, 110.0)
    data = _complete(years=short, revenue=pair, ebitda=pair, capex=pair, nwc=pair)
    assert len(data.years) < MIN_PERIODS
    assert data.available is False
