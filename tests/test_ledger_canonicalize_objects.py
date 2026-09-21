"""Canonicalization of structured objects that land in ledger hashes.

Dicts/enums/datetimes are already pinned in test_ledger_canonical.py. These
cover the dataclass and pydantic-shaped adapters: if they silently drop or
reorder fields, snapshot and context hashes fork without a schema bump.
"""
from __future__ import annotations

from dataclasses import dataclass

from gesh_core.ledger.canonical import canonicalize, content_hash


@dataclass
class _Holding:
    symbol: str
    quantity: float
    avg_cost: float | None = None


class _ModelDumpHolding:
    """Pydantic-v2 shaped: model_dump() is preferred over raw attributes."""

    def __init__(self, **fields: object) -> None:
        self._fields = fields
        self.extra_attr = "must-not-appear"

    def model_dump(self) -> dict[str, object]:
        return dict(self._fields)


class _V1Holding:
    """Pydantic-v1 shaped: .dict() is used only when __fields__ is present."""

    __fields__ = {"symbol": object(), "quantity": object()}

    def __init__(self, symbol: str, quantity: float) -> None:
        self.symbol = symbol
        self.quantity = quantity
        self.extra_attr = "must-not-appear"

    def dict(self) -> dict[str, object]:
        return {"symbol": self.symbol, "quantity": self.quantity}


def test_dataclass_matches_equivalent_dict():
    holding = _Holding(symbol="AAPL", quantity=2.0, avg_cost=180.0)
    as_dict = {"symbol": "AAPL", "quantity": 2.0, "avg_cost": 180.0}
    assert canonicalize(holding) == canonicalize(as_dict)
    assert content_hash(holding, prefix="ps") == content_hash(as_dict, prefix="ps")


def test_nested_dataclass_is_walked():
    payload = {"holdings": [_Holding(symbol="MSFT", quantity=1.0)]}
    out = canonicalize(payload)
    assert out["holdings"] == [{"avg_cost": None, "quantity": 1.0, "symbol": "MSFT"}]


def test_model_dump_is_preferred_over_attributes():
    obj = _ModelDumpHolding(symbol="NVDA", quantity=3)
    assert canonicalize(obj) == {"quantity": 3, "symbol": "NVDA"}
    assert "extra_attr" not in canonicalize(obj)


def test_pydantic_v1_dict_requires_fields_marker():
    obj = _V1Holding("AMD", 4.0)
    assert canonicalize(obj) == {"quantity": 4.0, "symbol": "AMD"}
    assert "extra_attr" not in canonicalize(obj)
