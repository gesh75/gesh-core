"""analysis_context_hash must include extra_versions in the identity.

A host that pins engine versions in extra_versions must get a new context
hash when those versions change — otherwise two runs over different engines
collide and look like an idempotent retry.
"""

from __future__ import annotations

from gesh_core.ledger.hashes import analysis_context_hash


def _ctx(**kwargs: object) -> str:
    return analysis_context_hash(
        tenant_id="owner",
        source="daily-chain",
        portfolio_snapshot_hash_value="ps_abc",
        **kwargs,
    )


def test_extra_versions_change_context_hash_and_are_deterministic():
    bare = _ctx()
    pinned = _ctx(extra_versions={"kelly_engine": "9.9.9"})
    again = _ctx(extra_versions={"kelly_engine": "9.9.9"})
    other = _ctx(extra_versions={"kelly_engine": "9.9.8"})
    assert pinned == again
    assert pinned != bare
    assert pinned != other
    assert pinned.startswith("ctx_")


def test_empty_extra_versions_matches_omitted():
    assert _ctx(extra_versions={}) == _ctx()
