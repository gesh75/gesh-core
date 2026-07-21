"""Canonical serialization and content hashing for ledger snapshots.

Rules (Phase 4A):
- Dictionary key order is normalized (sorted).
- Nested structures are walked recursively.
- Sets become sorted lists.
- datetimes become UTC ISO-8601 strings ending in Z.
- date becomes YYYY-MM-DD.
- Decimal is preserved as a string with a type tag.
- UUID becomes canonical str.
- Enums become their value.
- NaN / +/-Inf raise CanonicalizationError.
- Negative zero is normalized to 0.0.
- Input objects are never mutated.
- Known secret field names are rejected unless explicitly allowed.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

_SECRET_FIELD_NAMES = frozenset(
    {
        "password",
        "password_hash",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "authorization",
        "private_key",
    }
)


class CanonicalizationError(ValueError):
    """Raised when a value cannot be safely canonicalized for hashing."""


def _normalize_float(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        raise CanonicalizationError(f"non-finite float is not allowed in canonical form: {value!r}")
    if value == 0.0:
        return 0.0
    return value


def canonicalize(value: Any, *, _allow_secrets: bool = False) -> Any:
    """Return a JSON-compatible, order-stable representation of *value*.

    Does not mutate the input. Raises CanonicalizationError on unsafe values.
    """
    if value is None or isinstance(value, (bool, str, int)):
        return value

    if isinstance(value, float):
        return _normalize_float(value)

    if isinstance(value, Decimal):
        return {"__decimal__": format(value, "f")}

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Enum):
        return canonicalize(value.value, _allow_secrets=_allow_secrets)

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        else:
            value = value.astimezone(UTC)
        text = value.isoformat()
        if text.endswith("+00:00"):
            text = text[:-6] + "Z"
        return text

    if isinstance(value, date):
        return value.isoformat()

    if is_dataclass(value) and not isinstance(value, type):
        return canonicalize(asdict(value), _allow_secrets=_allow_secrets)

    if hasattr(value, "model_dump") and callable(value.model_dump):
        return canonicalize(value.model_dump(), _allow_secrets=_allow_secrets)
    if hasattr(value, "dict") and callable(value.dict) and hasattr(value, "__fields__"):
        return canonicalize(value.dict(), _allow_secrets=_allow_secrets)

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value.keys(), key=lambda k: str(k)):
            sk = str(key)
            if not _allow_secrets and sk.lower() in _SECRET_FIELD_NAMES:
                raise CanonicalizationError(
                    f"secret field {sk!r} is not allowed in canonical snapshot payloads"
                )
            out[sk] = canonicalize(value[key], _allow_secrets=_allow_secrets)
        return out

    if isinstance(value, (list, tuple)):
        return [canonicalize(item, _allow_secrets=_allow_secrets) for item in value]

    if isinstance(value, set):
        items = [canonicalize(item, _allow_secrets=_allow_secrets) for item in value]
        items.sort(
            key=lambda x: json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        )
        return items

    raise CanonicalizationError(f"unsupported type for canonicalization: {type(value).__name__}")


def canonical_json(value: Any, *, allow_secrets: bool = False) -> str:
    """Serialize *value* to a stable JSON string (UTF-8, sorted keys, no spaces)."""
    canonical = canonicalize(value, _allow_secrets=allow_secrets)
    return json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def content_hash(value: Any, *, prefix: str | None = None, allow_secrets: bool = False) -> str:
    """SHA-256 hex digest of the canonical JSON form of *value*.

    If *prefix* is provided, the digest is returned as ``{prefix}_{hex}``.
    """
    payload = canonical_json(value, allow_secrets=allow_secrets).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    if prefix:
        return f"{prefix}_{digest}"
    return digest
