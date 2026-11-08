"""Empty-string env for path/hour knobs is kept, not replaced by the default.

``_env_float`` / ``_env_int`` treat ``""`` as missing. ``os.getenv`` for
``KILL_SWITCH_PATH`` and ``MARKET_*`` does not — a launchd blank overwrites
the home-dir kill file and the 09:30/16:00 ET session. The gate then looks
at ``Path("").exists()`` (cwd) or compares against an empty hhmm. Pin the
current fail-open-to-blank behavior so a later default-restore is reviewable.
"""
from __future__ import annotations

from pathlib import Path

from gesh_core.trading.config import load_risk_config


def test_empty_kill_switch_path_is_not_restored_to_home(monkeypatch) -> None:
    monkeypatch.setenv("KILL_SWITCH_PATH", "")
    cfg = load_risk_config()
    assert cfg.kill_switch_path == ""
    assert cfg.kill_switch_path != str(Path.home() / ".gesh" / "KILL")


def test_empty_market_hours_are_not_restored_to_defaults(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_OPEN_HHMM", "")
    monkeypatch.setenv("MARKET_CLOSE_HHMM", "")
    monkeypatch.setenv("MARKET_TIMEZONE", "")
    cfg = load_risk_config()
    assert cfg.market_open_hhmm == ""
    assert cfg.market_close_hhmm == ""
    assert cfg.market_timezone == ""
