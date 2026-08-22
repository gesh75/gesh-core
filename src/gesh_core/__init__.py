"""gesh-core — shared modules for the GESH Financial engine and product repos.

Single source of truth for logic that was previously duplicated across
``gesh-project-trading`` (engine) and ``gesh-project`` (product). Phase 3
extracts modules here one at a time; each consumer keeps a thin re-export
shim so existing import paths (e.g. ``import allocation_config``) keep working.

Keep this module import-light: no heavy/optional dependencies at package import
time, so ``import gesh_core`` stays cheap for both consumers.
"""

__version__ = "0.8.2"
