"""Astra R7: isolate DB path and deny network before collection.

Importing gesh_core.db / trading.state must not CREATE/DROP against a
developer or CI checkout. Tests that need a specific path monkeypatch
GESH_DB_PATH or module DB_PATH after this session default is set.
"""

from __future__ import annotations

import os
import shutil
import socket
import tempfile
from pathlib import Path

import pytest


class _NetworkBlocked(RuntimeError):
    """Raised if a test or import attempts a real network connection."""


def pytest_configure(config: pytest.Config) -> None:
    root = Path(tempfile.mkdtemp(prefix="gesh-core-test-"))
    config._gesh_r7_root = root  # type: ignore[attr-defined]
    os.environ["GESH_DB_PATH"] = str(root / "gesh_financial.db")

    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise _NetworkBlocked("Network access attempted during gesh-core collection or tests")

    config._gesh_orig_connect = socket.socket.connect  # type: ignore[attr-defined]
    socket.socket.connect = _blocked  # type: ignore[method-assign]


def pytest_unconfigure(config: pytest.Config) -> None:
    orig = getattr(config, "_gesh_orig_connect", None)
    if orig is not None:
        socket.socket.connect = orig  # type: ignore[method-assign]
    root = getattr(config, "_gesh_r7_root", None)
    if root is not None:
        shutil.rmtree(root, ignore_errors=True)
