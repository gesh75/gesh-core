"""``config_hash`` participates in the analysis context hash.

Caps, gates, and Kelly knobs travel through optional ``config_hash``.
Different hashes must fork ``ctx_*``; ``None`` and omitted must match.
Pin that so config drift cannot reuse a decision identity. ``extra_versions``
sensitivity is already claimed elsewhere.
"""
from __future__ import annotations

from gesh_core.ledger.hashes import analysis_context_hash


def _kwargs(**extra):
    base = dict(
        tenant_id="owner",
        source="daily-chain",
        portfolio_snapshot_hash_value="ps_abc",
        market_quote_snapshot_hashes=["mqs_1"],
    )
    base.update(extra)
    return base


def test_config_hash_changes_context_hash() -> None:
    a = analysis_context_hash(**_kwargs(config_hash="cfg_a"))
    b = analysis_context_hash(**_kwargs(config_hash="cfg_b"))
    assert a != b
    assert a.startswith("ctx_")
    assert b.startswith("ctx_")


def test_identical_config_hash_is_stable() -> None:
    a = analysis_context_hash(**_kwargs(config_hash="cfg_a"))
    b = analysis_context_hash(**_kwargs(config_hash="cfg_a"))
    assert a == b


def test_omitted_and_none_config_hash_match() -> None:
    omitted = analysis_context_hash(**_kwargs())
    explicit_none = analysis_context_hash(**_kwargs(config_hash=None))
    assert omitted == explicit_none
