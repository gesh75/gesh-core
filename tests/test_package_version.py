"""Regression test ensuring pyproject.toml and runtime __version__ stay in sync."""

import tomllib
from pathlib import Path

import gesh_core


def test_package_and_runtime_version_match():
    """pyproject.toml version must equal gesh_core.__version__."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    declared = data["project"]["version"]
    runtime = gesh_core.__version__

    # Declared as a LITERAL on purpose: bumping the version then requires editing
    # this line, so the release is reviewable rather than incidental.
    #
    # 0.7.0 = the gesh_core.dcf package (shared deterministic DCF valuation,
    # extracted from gesh-project-trading — engine PRs #104/#108). Minor bump:
    # additive public API (compute_fair_value, run_sensitivity, DCFInputs,
    # value_with_assumptions), no changes to existing modules.
    assert declared == "0.7.0"
    assert runtime == "0.7.0"
    assert declared == runtime
