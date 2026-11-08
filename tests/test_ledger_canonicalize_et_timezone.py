"""Aware non-UTC timestamps must canonicalize to the same UTC instant.

Ledger hashes treat naive datetimes as UTC. An America/New_York wall clock
must convert, not be stringified in local offset — otherwise two recordings
of the same instant (ET vs Z) get different snapshot hashes and the
idempotent retry path looks like a conflict.
"""
from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from gesh_core.ledger.canonical import CanonicalizationError, canonicalize, content_hash


def test_eastern_wall_clock_matches_equivalent_utc() -> None:
    # 2026-01-15 is standard time (UTC−5): 12:00 ET == 17:00Z.
    et = datetime(2026, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    utc = datetime(2026, 1, 15, 17, 0, 0, tzinfo=UTC)
    assert canonicalize(et) == "2026-01-15T17:00:00Z"
    assert canonicalize(et) == canonicalize(utc)
    assert content_hash({"t": et}) == content_hash({"t": utc})


def test_allow_secrets_includes_secret_fields() -> None:
    payload = {"api_key": "sk-test", "symbol": "NVDA"}
    with pytest.raises(CanonicalizationError, match="secret field"):
        content_hash(payload)
    digest = content_hash(payload, allow_secrets=True)
    assert digest != content_hash({"symbol": "NVDA"}, allow_secrets=True)
