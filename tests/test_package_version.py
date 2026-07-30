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
    # 0.6.2 distinguishes this tree from the v0.6.1 TAG. Commits d4e9f46 (strict
    # safety booleans) and 478cb89 landed after that tag while still declaring
    # "0.6.1", so a version comparison could not tell the two trees apart and
    # consumers had to pin by commit SHA to be unambiguous.
    assert declared == "0.6.2"
    assert runtime == "0.6.2"
    assert declared == runtime
