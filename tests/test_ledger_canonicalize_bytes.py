"""Bytes / bytearray are unsupported in canonical ledger payloads.

A host that stuffs a raw quote frame or secret material as bytes must
fail closed (CanonicalizationError) rather than hashing repr() or
silently dropping the field. Distinct from the dataclass/pydantic object
adapters already claimed elsewhere.
"""

from __future__ import annotations

import pytest

from gesh_core.ledger.canonical import CanonicalizationError, canonicalize, content_hash


@pytest.mark.parametrize("value", [b"secret", bytearray(b"frame"), memoryview(b"x")])
def test_bytes_like_values_are_rejected(value):
    with pytest.raises(CanonicalizationError, match="unsupported type"):
        canonicalize(value)


def test_nested_bytes_field_rejects_the_whole_payload():
    with pytest.raises(CanonicalizationError, match="unsupported type"):
        content_hash({"symbol": "NVDA", "raw": b"\x00\x01"})
