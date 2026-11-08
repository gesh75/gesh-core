"""version_bundle must omit the recommendation-ID schema version.

RECOMMENDATION_ID_SCHEMA_VERSION versions the ID scheme (v2 added normalized
decision_at), not the decision input context. Including it in version_bundle
would churn every context_hash on an ID-scheme bump and break idempotent
ledger writes for unchanged decisions.
"""
from __future__ import annotations

from gesh_core.ledger.canonical import content_hash
from gesh_core.ledger.hashes import analysis_context_hash
from gesh_core.ledger.versions import (
    RECOMMENDATION_ID_SCHEMA_VERSION,
    version_bundle,
)


def test_version_bundle_omits_recommendation_id_schema():
    bundle = version_bundle()
    assert "recommendation_id_schema" not in bundle
    assert RECOMMENDATION_ID_SCHEMA_VERSION == 2
    assert "recommendation_id" not in "".join(bundle.keys())


def test_context_hash_stable_if_id_schema_constant_changes_locally():
    # Extra ID-scheme keys must not already be in the hashed bundle.
    base = analysis_context_hash(
        tenant_id="owner",
        source="daily",
        portfolio_snapshot_hash_value="ps_abc",
    )
    extra = analysis_context_hash(
        tenant_id="owner",
        source="daily",
        portfolio_snapshot_hash_value="ps_abc",
        extra_versions={"recommendation_id_schema": RECOMMENDATION_ID_SCHEMA_VERSION + 1},
    )
    assert base != extra
    assert content_hash(version_bundle()) != content_hash(
        {**version_bundle(), "recommendation_id_schema": 99}
    )
