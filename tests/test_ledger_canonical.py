"""Tests for ledger canonicalization, content hashing, and version contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from gesh_core.ledger.canonical import (
    CanonicalizationError,
    canonical_json,
    canonicalize,
    content_hash,
)
from gesh_core.ledger.hashes import (
    analysis_context_hash,
    market_quote_snapshot_hash,
    portfolio_snapshot_hash,
)
from gesh_core.ledger.versions import (
    OWNER_TENANT_ID,
    RECOMMENDATION_ID_SCHEMA_VERSION,
    version_bundle,
)


def test_dict_order_independent():
    a = {"b": 1, "a": 2}
    b = {"a": 2, "b": 1}
    assert content_hash(a) == content_hash(b)
    assert canonical_json(a) == canonical_json(b)


def test_nested_structures():
    left = {"outer": {"inner": [1, {"k": "v"}]}, "n": None}
    right = {"n": None, "outer": {"inner": [1, {"k": "v"}]}}
    assert content_hash(left) == content_hash(right)


def test_set_deterministic():
    assert content_hash({3, 1, 2}) == content_hash({2, 3, 1})


def test_decimal_normalization():
    d = Decimal("123.456789")
    assert canonicalize(d) == {"__decimal__": "123.456789"}
    assert content_hash({"x": d}) == content_hash({"x": Decimal("123.456789")})


def test_datetime_and_date_normalization():
    naive = datetime(2026, 1, 15, 12, 0, 0)
    aware = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    assert canonicalize(naive) == canonicalize(aware)
    assert canonicalize(naive).endswith("Z")
    assert canonicalize(date(2026, 7, 21)) == "2026-07-21"


def test_negative_zero_normalized():
    assert canonicalize(-0.0) == 0.0
    assert content_hash(-0.0) == content_hash(0.0)


def test_nan_rejected():
    with pytest.raises(CanonicalizationError):
        canonicalize(float("nan"))


def test_infinity_rejected():
    with pytest.raises(CanonicalizationError):
        canonicalize(float("inf"))
    with pytest.raises(CanonicalizationError):
        canonicalize(float("-inf"))


def test_unsupported_type_rejected():
    with pytest.raises(CanonicalizationError):
        canonicalize(object())


def test_secret_field_rejected():
    with pytest.raises(CanonicalizationError, match="secret field"):
        canonicalize({"api_key": "sk-test"})
    with pytest.raises(CanonicalizationError, match="secret field"):
        canonicalize({"password": "x"})


def test_canonicalize_secret_field_case_insensitive_raises():
    with pytest.raises(CanonicalizationError, match="secret field"):
        canonicalize({"API_KEY": "sk-test"})
    with pytest.raises(CanonicalizationError, match="secret field"):
        canonicalize({"Token": "x"})


def test_canonicalize_nested_secret_field_raises():
    with pytest.raises(CanonicalizationError, match="secret field"):
        canonicalize({"risk_state": {"access_token": "nested-secret"}})


def test_canonicalize_allow_secrets_permits_api_key():
    payload = {"api_key": "sk-test"}
    assert canonicalize(payload, _allow_secrets=True) == payload
    assert "sk-test" in canonical_json(payload, allow_secrets=True)


def test_canonicalize_non_utc_datetime_converts_to_z():
    eastern = datetime(2026, 1, 15, 7, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    assert canonicalize(eastern) == "2026-01-15T12:00:00Z"


@dataclass
class _Holding:
    symbol: str
    qty: int


def test_canonicalize_dataclass_produces_stable_hash():
    holding = _Holding(symbol="AAPL", qty=1)
    as_dict = {"symbol": "AAPL", "qty": 1}
    assert canonicalize(holding) == canonicalize(as_dict)
    assert content_hash(holding) == content_hash(as_dict)


def test_input_not_mutated():
    original = {"z": 1, "a": [2, 3]}
    snapshot = dict(original)
    canonicalize(original)
    assert original == snapshot


class _Color(Enum):
    RED = "red"


def test_enum_uuid_and_prefix():
    uid = UUID("12345678-1234-5678-1234-567812345678")
    assert canonicalize(_Color.RED) == "red"
    assert canonicalize(uid) == str(uid)
    assert content_hash({"x": 1}, prefix="ps").startswith("ps_")


def test_version_bundle_sensitive_to_engine_change():
    b = version_bundle()
    assert b["ledger_schema"] == 1
    assert OWNER_TENANT_ID == "owner"
    altered = {**b, "kelly_engine": "9.9.9"}
    assert content_hash(b) != content_hash(altered)


def test_version_bundle_excludes_recommendation_id_schema():
    bundle = version_bundle()
    assert "recommendation_id_schema" not in bundle
    assert RECOMMENDATION_ID_SCHEMA_VERSION == 2


def test_portfolio_hash_deterministic_and_sorted_holdings():
    h1 = portfolio_snapshot_hash(
        tenant_id="owner",
        holdings=[{"symbol": "msft", "quantity": 2}, {"symbol": "AAPL", "qty": 1}],
        cash=100.0,
        buying_power=100.0,
        total_equity=500.0,
    )
    h2 = portfolio_snapshot_hash(
        tenant_id="owner",
        holdings=[{"symbol": "AAPL", "quantity": 1}, {"symbol": "MSFT", "quantity": 2}],
        cash=100.0,
        buying_power=100.0,
        total_equity=500.0,
    )
    assert h1 == h2
    assert h1.startswith("ps_")


def test_portfolio_hash_shares_alias_matches_quantity():
    kwargs = dict(
        tenant_id="owner",
        cash=0.0,
        buying_power=0.0,
        total_equity=10.0,
    )
    via_shares = portfolio_snapshot_hash(
        holdings=[{"symbol": "AAPL", "shares": 3}], **kwargs
    )
    via_qty = portfolio_snapshot_hash(holdings=[{"symbol": "AAPL", "quantity": 3}], **kwargs)
    assert via_shares == via_qty


def test_portfolio_hash_average_cost_alias_matches_avg_cost():
    kwargs = dict(
        tenant_id="owner",
        cash=0.0,
        buying_power=0.0,
        total_equity=10.0,
    )
    via_alias = portfolio_snapshot_hash(
        holdings=[{"symbol": "AAPL", "quantity": 1, "average_cost": 12.5}], **kwargs
    )
    via_canonical = portfolio_snapshot_hash(
        holdings=[{"symbol": "AAPL", "quantity": 1, "avg_cost": 12.5}], **kwargs
    )
    assert via_alias == via_canonical


def test_portfolio_hash_risk_state_changes_digest():
    kwargs = dict(
        tenant_id="owner",
        holdings=[{"symbol": "AAPL", "quantity": 1}],
        cash=0.0,
        buying_power=0.0,
        total_equity=10.0,
    )
    plain = portfolio_snapshot_hash(**kwargs)
    gated = portfolio_snapshot_hash(**kwargs, risk_state={"portfolio_gate": "COOLING"})
    assert plain != gated


def test_context_hash_extra_versions_overrides_bundle():
    kwargs = dict(
        tenant_id="owner",
        source="daily-chain",
        portfolio_snapshot_hash_value="ps_abc",
        market_quote_snapshot_hashes=["mqs_1"],
    )
    base = analysis_context_hash(**kwargs)
    overridden = analysis_context_hash(**kwargs, extra_versions={"kelly_engine": "9.9.9"})
    assert base != overridden
    assert overridden == analysis_context_hash(
        **kwargs, extra_versions={"kelly_engine": "9.9.9"}
    )


def test_portfolio_hash_tenant_sensitive():
    kwargs = dict(
        holdings=[{"symbol": "AAPL", "quantity": 1}],
        cash=0.0,
        buying_power=0.0,
        total_equity=10.0,
    )
    assert portfolio_snapshot_hash(tenant_id="t1", **kwargs) != portfolio_snapshot_hash(
        tenant_id="t2", **kwargs
    )


def test_market_quote_hash_deterministic():
    kwargs = dict(
        tenant_id="owner",
        symbol="nvda",
        provider="yahoo",
        as_of="2026-07-21T14:00:00Z",
        bid=100.0,
        ask=100.1,
        last=100.05,
        quality_state="FRESH",
    )
    a = market_quote_snapshot_hash(**kwargs)
    b = market_quote_snapshot_hash(**kwargs)
    assert a == b
    assert a.startswith("mqs_")
    # Symbol case normalized
    c = market_quote_snapshot_hash(**{**kwargs, "symbol": "NVDA"})
    assert a == c


def test_context_hash_deterministic_and_prefixed():
    ctx = analysis_context_hash(
        tenant_id="owner",
        source="daily-chain",
        portfolio_snapshot_hash_value="ps_abc",
        market_quote_snapshot_hashes=["mqs_1", "mqs_2"],
    )
    ctx2 = analysis_context_hash(
        tenant_id="owner",
        source="daily-chain",
        portfolio_snapshot_hash_value="ps_abc",
        market_quote_snapshot_hashes=["mqs_1", "mqs_2"],
    )
    assert ctx == ctx2
    assert ctx.startswith("ctx_")
    # Order of market quote hashes matters (ordered list)
    ctx3 = analysis_context_hash(
        tenant_id="owner",
        source="daily-chain",
        portfolio_snapshot_hash_value="ps_abc",
        market_quote_snapshot_hashes=["mqs_2", "mqs_1"],
    )
    assert ctx != ctx3
