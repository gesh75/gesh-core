"""Ledger leftover: ``client_secret`` is not in the canonical denylist.

P2-8: adapter/canonical strip ``api_key`` / ``secret`` / ``token`` but not
``client_secret`` / ``reddit_client_secret`` (this package's Reddit env).
Pin current behavior so adding them is a deliberate denylist change, not a
silent hash fork.
"""

from __future__ import annotations

import pytest

from gesh_core.ledger.canonical import CanonicalizationError, canonicalize


def test_api_key_still_rejected() -> None:
    with pytest.raises(CanonicalizationError, match="secret field"):
        canonicalize({"api_key": "sk-test"})


def test_client_secret_currently_passes_through() -> None:
    out = canonicalize({"client_secret": "reddit-app-secret", "symbol": "NVDA"})
    assert out == {"client_secret": "reddit-app-secret", "symbol": "NVDA"}


def test_reddit_client_secret_currently_passes_through() -> None:
    out = canonicalize({"REDDIT_CLIENT_SECRET": "reddit-app-secret"})
    assert out["REDDIT_CLIENT_SECRET"] == "reddit-app-secret"
