"""Portfolio snapshot hash field-alias stability.

Engine and product hosts disagree on holding keys (`quantity`/`qty`/`shares`,
`avg_cost`/`average_cost`). The hash must collapse those aliases so the same
book does not fork into duplicate snapshots and break ledger idempotency.
"""

from __future__ import annotations

from gesh_core.ledger.hashes import portfolio_snapshot_hash


def _hash(holdings: list[dict]) -> str:  # values are host-shaped mappings
    return portfolio_snapshot_hash(
        tenant_id="owner",
        holdings=holdings,
        cash=10.0,
        buying_power=10.0,
        total_equity=100.0,
    )


def test_quantity_qty_and_shares_aliases_hash_identically():
    expected = _hash([{"symbol": "AAPL", "quantity": 3, "avg_cost": 150.0}])
    assert _hash([{"symbol": "AAPL", "qty": 3, "avg_cost": 150.0}]) == expected
    assert _hash([{"symbol": "AAPL", "shares": 3, "avg_cost": 150.0}]) == expected


def test_avg_cost_and_average_cost_aliases_hash_identically():
    expected = _hash([{"symbol": "msft", "quantity": 2, "avg_cost": 400.0}])
    assert _hash([{"symbol": "MSFT", "quantity": 2, "average_cost": 400.0}]) == expected


def test_avg_cost_wins_when_both_cost_keys_are_present():
    expected = _hash([{"symbol": "AAPL", "quantity": 3, "avg_cost": 150.0}])
    both = _hash([{"symbol": "AAPL", "quantity": 3, "avg_cost": 150.0, "average_cost": 999.0}])
    assert both == expected


def test_different_cost_or_qty_changes_hash():
    base = _hash([{"symbol": "AAPL", "quantity": 3, "avg_cost": 150.0}])
    assert _hash([{"symbol": "AAPL", "quantity": 3, "avg_cost": 151.0}]) != base
    assert _hash([{"symbol": "AAPL", "shares": 4, "avg_cost": 150.0}]) != base
