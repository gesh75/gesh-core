"""Leftover Kelly overlay: a garbage correlation threshold keeps the default.

Position/gross caps fail construction on junk (#79). The clustering threshold
is still a soft overlay — ``abc`` / blank must not become 0 and disable every
haircut (a 0 threshold would treat any finite corr as a cluster and shrink
the whole book).
"""

from __future__ import annotations

import pytest

from gesh_core import kelly


@pytest.mark.parametrize("raw", ["abc", " ", "corr"])
def test_garbage_corr_threshold_keeps_default(monkeypatch, raw: str) -> None:
    monkeypatch.setenv("KELLY_CORR_THRESHOLD", raw)
    assert kelly._corr_threshold() == pytest.approx(0.70)
