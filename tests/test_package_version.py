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

    assert declared == "0.6.0"
    assert runtime == "0.6.0"
    assert declared == runtime
