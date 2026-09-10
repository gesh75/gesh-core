"""``DCFInputs.available`` requires every series to share ``years`` length.

DCFModel consumes these as positional lists. A short ``nwc`` beside a full
``revenue`` would pair the wrong fiscal years without raising — the same
class of silent misalignment ``kelly._fetch_returns`` documents. Pin the
contract so a later "best-effort zip" cannot ship a misdated valuation.
"""

from __future__ import annotations

from gesh_core.dcf.inputs import DCFInputs


def test_available_false_when_nwc_shorter_than_years():
    data = DCFInputs(
        symbol="AMD",
        years=(2023, 2024, 2025),
        revenue=(20_000.0, 22_000.0, 25_000.0),
        ebitda=(5_000.0, 6_000.0, 7_500.0),
        capex=(1_000.0, 1_100.0, 1_250.0),
        nwc=(4_000.0, 4_400.0),  # one year short
        tax_rate=0.15,
        shares_outstanding=1_600.0,
        net_debt=-2_000.0,
    )
    assert data.available is False


def test_available_false_when_missing_is_nonempty_even_if_lengths_match():
    data = DCFInputs(
        symbol="AMD",
        years=(2023, 2024, 2025),
        revenue=(20_000.0, 22_000.0, 25_000.0),
        ebitda=(5_000.0, 6_000.0, 7_500.0),
        capex=(1_000.0, 1_100.0, 1_250.0),
        nwc=(4_000.0, 4_400.0, 5_000.0),
        tax_rate=0.15,
        shares_outstanding=1_600.0,
        net_debt=-2_000.0,
        missing=("tax_rate",),
    )
    assert data.available is False
