"""A holding with no quantity/qty/shares hashes as quantity=None, not 0.

Dropping the size field must not collide with an explicit zero position —
that would let an empty book share a portfolio snapshot hash with a
closed-out name and hide a real position change from the audit trail.
"""

from __future__ import annotations

from gesh_core.ledger.hashes import portfolio_snapshot_hash


def _hash(holdings):
    return portfolio_snapshot_hash(
        tenant_id="owner",
        holdings=holdings,
        cash=100.0,
        buying_power=100.0,
        total_equity=500.0,
    )


def test_missing_quantity_forks_hash_from_explicit_zero():
    missing = _hash([{"symbol": "AAPL"}])
    zero = _hash([{"symbol": "AAPL", "quantity": 0}])
    none = _hash([{"symbol": "AAPL", "quantity": None}])
    assert missing == none
    assert missing != zero
    assert missing.startswith("ps_")
