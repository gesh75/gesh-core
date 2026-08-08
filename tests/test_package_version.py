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
    # 0.8.0 = DCF methodology revision (2026-08-08 practitioner review): operating
    # NWC definition, Blume-adjusted beta default + fragility flag, multi-year-average
    # ratio base case, sector/margin/non-positive refusals, re-derived guards.
    # OUTPUT-CHANGING for every fair value — hence minor, not patch.
    assert declared == "0.8.0"
    assert runtime == "0.8.0"
    assert declared == runtime
