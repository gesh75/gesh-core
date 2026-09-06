"""Parity tests for gesh_core.tax_harvester (Phase 3.3).

Pins the env-driven DB resolver (the reason this module was deferred from earlier
phases) AND the scan/wash-sale logic. All DB writes go to a tmp path via
GESH_TRACKER_DB so the real gesh_financial.db is never touched.
"""
from __future__ import annotations

import sqlite3

import pytest

from gesh_core import tax_harvester as th


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    # Every test resolves the wash_sale_log DB to an isolated tmp file.
    monkeypatch.setenv("GESH_TRACKER_DB", str(tmp_path / "gesh_financial.db"))
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)
    yield


def test_module_loads_from_gesh_core():
    assert "gesh_core" in (th.__file__ or "")


# ─── DB resolver precedence ───────────────────────────────────────────────────

def test_resolver_prefers_explicit_tracker_db(tmp_path, monkeypatch):
    target = tmp_path / "explicit.db"
    monkeypatch.setenv("GESH_TRACKER_DB", str(target))
    assert th._primary_db() == target


def test_resolver_uses_trading_home(tmp_path, monkeypatch):
    monkeypatch.delenv("GESH_TRACKER_DB", raising=False)
    monkeypatch.setenv("GESH_TRADING_HOME", str(tmp_path))
    assert th._primary_db() == tmp_path / "gesh_financial.db"


def test_resolver_falls_back_to_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("GESH_TRACKER_DB", raising=False)
    monkeypatch.delenv("GESH_TRADING_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    assert th._primary_db() == tmp_path / "gesh_financial.db"


def test_unusable_primary_fails_closed(tmp_path, monkeypatch):
    """A corrupt wash-sale ledger must never be replaced by an empty DB."""
    target = tmp_path / "corrupt.db"
    target.write_bytes(b"not a sqlite database")
    monkeypatch.setenv("GESH_TRACKER_DB", str(target))

    with pytest.raises(sqlite3.DatabaseError):
        th.get_wash_status("GGG")


# ─── scan_tax_loss_candidates ─────────────────────────────────────────────────

def test_no_cost_basis_surfaced_not_zeroed():
    positions = {"AAA": {"price": 10.0, "quantity": 5}}  # no basis
    cands = th.scan_tax_loss_candidates(positions, cost_basis_map={})
    rec = cands[0]
    assert rec["status"] == "NO_COST_BASIS"
    assert rec["unrealised_loss_usd"] is None      # never fabricated as break-even


def test_real_loss_eligible():
    # $800 loss (> $500 threshold) -> ELIGIBLE
    positions = {"BBB": {"price": 80.0, "quantity": 20, "average_buy_price": 120.0}}
    cands = th.scan_tax_loss_candidates(positions)
    rec = cands[0]
    assert rec["unrealised_loss_usd"] == pytest.approx(-800.0)
    assert rec["status"] == "ELIGIBLE"


def test_below_threshold_loss():
    positions = {"CCC": {"price": 99.0, "quantity": 1, "average_buy_price": 120.0}}  # -$21
    cands = th.scan_tax_loss_candidates(positions)
    assert cands[0]["status"] == "BELOW_THRESHOLD"


def test_profitable_position_skipped():
    positions = {"DDD": {"price": 130.0, "quantity": 10, "average_buy_price": 100.0}}
    assert th.scan_tax_loss_candidates(positions) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("price", "nan"),
        ("price", "inf"),
        ("quantity", "nan"),
        ("quantity", "inf"),
        ("average_buy_price", "nan"),
        ("average_buy_price", "inf"),
    ],
)
def test_non_finite_position_values_are_skipped(field, value):
    position = {"price": 50.0, "quantity": 20, "average_buy_price": 100.0}
    position[field] = value

    assert th.scan_tax_loss_candidates({"BAD": position}) == []


def test_cost_basis_map_overrides_position():
    positions = {"EEE": {"price": 50.0, "quantity": 100}}  # $5000 loss vs basis 100
    cands = th.scan_tax_loss_candidates(positions, cost_basis_map={"EEE": 100.0})
    assert cands[0]["unrealised_loss_usd"] == pytest.approx(-5000.0)
    assert cands[0]["status"] == "ELIGIBLE"


# ─── wash-sale window ─────────────────────────────────────────────────────────

def test_record_harvest_starts_wash_window():
    th.record_harvest("FFF", sale_price=10.0, loss_usd=600.0)
    status = th.get_wash_status("FFF")
    assert status["in_wash_window"] is True
    assert status["days_remaining"] > 0 and status["days_remaining"] <= th.WASH_SALE_DAYS


def test_harvested_position_flagged_in_wash_window():
    th.record_harvest("GGG", sale_price=80.0, loss_usd=400.0)
    positions = {"GGG": {"price": 80.0, "quantity": 10, "average_buy_price": 120.0}}
    cands = th.scan_tax_loss_candidates(positions)
    assert cands[0]["status"] == "IN_WASH_WINDOW"


def test_unknown_ticker_no_wash_window():
    assert th.get_wash_status("ZZZ") == {
        "in_wash_window": False, "wash_safe_date": None, "days_remaining": 0}


def test_wash_window_includes_day_30(monkeypatch):
    """Repurchase on sale+30 is still a wash sale (IRS Pub 550).

    Trigger: harvest on 2026-01-01, rebuy on the stored wash_safe_date
    (2026-01-31). The old `>` comparison cleared the window that morning.
    """

    class FrozenDate(th.date):
        _today = th.date(2026, 1, 1)

        @classmethod
        def today(cls):
            return cls._today

    monkeypatch.setattr(th, "date", FrozenDate)
    th.record_harvest("WWW", sale_price=10.0, loss_usd=600.0)
    assert th.get_wash_status("WWW")["wash_safe_date"] == "2026-01-31"

    FrozenDate._today = th.date(2026, 1, 31)
    last_day = th.get_wash_status("WWW")
    assert last_day["in_wash_window"] is True
    positions = {"WWW": {"price": 8.0, "quantity": 100, "average_buy_price": 20.0}}
    assert th.scan_tax_loss_candidates(positions)[0]["status"] == "IN_WASH_WINDOW"

    FrozenDate._today = th.date(2026, 2, 1)
    assert th.get_wash_status("WWW")["in_wash_window"] is False


# ─── get_harvest_summary ──────────────────────────────────────────────────────

def test_harvest_summary_counts_and_generated_at():
    positions = {
        "H1": {"price": 50.0, "quantity": 100, "average_buy_price": 120.0},  # eligible
        "H2": {"price": 10.0, "quantity": 5},                                # no basis
    }
    out = th.get_harvest_summary(positions)
    assert out["eligible_count"] == 1
    assert out["no_cost_basis_count"] == 1
    assert out["total_harvestable_loss_usd"] > 0
    # generated_at is a naive ISO timestamp (no offset suffix), non-deprecated form
    assert "+00:00" not in out["generated_at"]
    assert "T" in out["generated_at"]


# ─── Connection lifecycle (H1: no leaked SQLite connections) ───────────────────

def test_no_leaked_connections(monkeypatch):
    """Every SQLite connection tax_harvester opens must be closed (H1).

    sqlite3's connection context manager commits but does NOT close; the prior
    `with _get_conn() as conn:` pattern leaked a handle on every call, which
    accumulated across each autopilot scan. A closed connection raises
    ProgrammingError on use, so we assert every opened connection is closed.
    """
    import sqlite3 as _sqlite

    real_connect = th.sqlite3.connect
    opened: list[_sqlite.Connection] = []

    def tracking_connect(*args, **kwargs):
        con = real_connect(*args, **kwargs)
        opened.append(con)
        return con

    monkeypatch.setattr(th.sqlite3, "connect", tracking_connect)

    th.record_harvest("NVDA", 100.0, -500.0)
    th.get_wash_status("NVDA")

    assert opened, "expected tax_harvester to open at least one connection"
    for con in opened:
        with pytest.raises(_sqlite.ProgrammingError):
            con.execute("SELECT 1")  # raises only if the connection was closed
