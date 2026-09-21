"""_require_tenant rejects blank / whitespace-only tenant ids after strip.

Ledger rows are tenant-scoped. An empty string is already rejected on the
insert path; a whitespace-only id would otherwise store as a real tenant
and isolate (or collide with) later stripped lookups.
"""
from __future__ import annotations

import pytest

from gesh_core.ledger import repository as repo


def test_require_tenant_strips_surrounding_whitespace() -> None:
    assert repo._require_tenant(" acme ") == "acme"
    assert repo._require_tenant("\tacme\n") == "acme"


def test_require_tenant_rejects_whitespace_only() -> None:
    for bad in ("", "   ", "\t", "\n"):
        with pytest.raises(ValueError, match="tenant_id is required"):
            repo._require_tenant(bad)
