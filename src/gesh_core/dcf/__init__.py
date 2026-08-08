"""Deterministic DCF valuation — shared by the engine (:9003) and product (:9000).

Extracted from gesh-project-trading (PR #104/#108 lineage) per rule #46: shared
logic lives in gesh-core, consumers keep transparent shims. MEASUREMENT ONLY —
nothing here places trades or writes engine databases.
"""
from gesh_core.dcf.fair_value import compute_fair_value, value_with_assumptions
from gesh_core.dcf.inputs import DCFInputs, fetch_dcf_inputs
from gesh_core.dcf.sensitivity import run_sensitivity

__all__ = ["DCFInputs", "compute_fair_value", "fetch_dcf_inputs",
           "run_sensitivity", "value_with_assumptions"]
