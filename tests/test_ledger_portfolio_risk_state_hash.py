"""Portfolio ``risk_state`` participates in the snapshot hash.

ECG / risk-gate posture is hashed into ``ps_*``. A COOLING vs missing
``risk_state`` must fork identity; identical posture must stay stable.
``None`` and omitted default are the same. Pin that so a later exclusion
cannot silently reuse recommendation IDs across a posture change.
"""
from __future__ import annotations

from gesh_core.ledger.hashes import portfolio_snapshot_hash


def _kwargs(**extra):
    base = dict(
        tenant_id="owner",
        holdings=[{"symbol": "AAPL", "quantity": 1, "avg_cost": 10.0}],
        cash=100.0,
        buying_power=100.0,
        total_equity=500.0,
    )
    base.update(extra)
    return base


def test_risk_state_changes_portfolio_hash() -> None:
    none_hash = portfolio_snapshot_hash(**_kwargs(risk_state=None))
    cooling = portfolio_snapshot_hash(**_kwargs(risk_state={"ecg": "COOLING"}))
    assert none_hash != cooling
    assert none_hash.startswith("ps_")
    assert cooling.startswith("ps_")


def test_identical_risk_state_is_stable() -> None:
    a = portfolio_snapshot_hash(**_kwargs(risk_state={"ecg": "HEALTHY"}))
    b = portfolio_snapshot_hash(**_kwargs(risk_state={"ecg": "HEALTHY"}))
    assert a == b


def test_omitted_and_none_risk_state_match() -> None:
    omitted = portfolio_snapshot_hash(**_kwargs())
    explicit_none = portfolio_snapshot_hash(**_kwargs(risk_state=None))
    assert omitted == explicit_none
