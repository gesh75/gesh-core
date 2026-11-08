"""``_parse_position_cap`` must fail safe on un-floatable values.

Env parsing already covers garbage strings. The TypeError branch is the
call-time seam: a list or object must not raise into consensus / the
/kelly dashboard.
"""

from __future__ import annotations

from gesh_core import kelly


def test_parse_position_cap_non_string_falls_back() -> None:
    assert kelly._parse_position_cap(["0.18"], 0.25) == 0.25  # type: ignore[arg-type]
    assert kelly._parse_position_cap({"cap": 0.1}, 0.25) == 0.25  # type: ignore[arg-type]
    assert kelly._parse_position_cap(object(), 0.1) == 0.1  # type: ignore[arg-type]
