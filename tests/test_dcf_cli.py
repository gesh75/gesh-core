"""CLI wiring for ``python -m gesh_core.dcf`` and the inputs CLI.

v0.8.2 fixed the module paths (they still named pre-extraction
``trading.dcf_*``). These tests pin the public CLIs to the shared package
without hitting the network.
"""
from __future__ import annotations

import json
import sys

from gesh_core.dcf import fair_value as fv
from gesh_core.dcf import inputs as dcf_inputs
from gesh_core.dcf.inputs import DCFInputs


def test_dcf_package_cli_binds_fair_value_main():
    from gesh_core.dcf import __main__ as dcf_main
    from gesh_core.dcf.fair_value import main as fv_main

    assert dcf_main.main is fv_main


def test_fair_value_cli_json_success_uppercases_symbol(monkeypatch, capsys):
    def fake(symbol: str, **kwargs: object) -> dict:
        assert symbol == "AMD"
        return {
            "symbol": symbol,
            "fair_value_per_share": 12.5,
            "enterprise_value_musd": 100.0,
            "equity_value_musd": 90.0,
            "wacc": 0.09,
            "terminal_pct_of_ev": 70.0,
            "inputs_fetched": {
                "years": [2023],
                "revenue": [20],
                "ebitda": [5],
                "capex": [1],
                "nwc": [4],
                "capex_pct": 0.05,
                "nwc_pct": 0.2,
                "tax_rate": 0.15,
                "shares_m": 1.6,
                "net_debt_musd": -2,
                "beta": 1.1,
                "beta_fetched": False,
            },
            "assumptions": {
                "revenue_growth": [0.08],
                "ebitda_margin_flat": 0.3,
                "terminal_growth": 0.03,
                "risk_free": 0.042,
                "market_premium": 0.055,
            },
        }

    monkeypatch.setattr(fv, "compute_fair_value", fake)
    monkeypatch.setattr(sys, "argv", ["dcf", "--symbol", "amd", "--json"])
    assert fv.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["symbol"] == "AMD"
    assert payload["fair_value_per_share"] == 12.5


def test_fair_value_cli_json_error_exits_one(monkeypatch, capsys):
    monkeypatch.setattr(
        fv,
        "compute_fair_value",
        lambda symbol, **k: {"symbol": symbol, "error": "missing inputs"},
    )
    monkeypatch.setattr(sys, "argv", ["dcf", "--symbol", "ZZZ", "--json"])
    assert fv.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "missing inputs"


def test_fair_value_cli_text_error_exits_one(monkeypatch, capsys):
    monkeypatch.setattr(
        fv,
        "compute_fair_value",
        lambda symbol, **k: {"symbol": symbol, "error": "sector 'Financials'"},
    )
    monkeypatch.setattr(sys, "argv", ["dcf", "--symbol", "JPM"])
    assert fv.main() == 1
    out = capsys.readouterr().out
    assert "JPM" in out
    assert "Financials" in out


def test_inputs_cli_json_unavailable_exits_one(monkeypatch, capsys):
    monkeypatch.setattr(
        dcf_inputs,
        "fetch_dcf_inputs",
        lambda symbol, periods=3: DCFInputs(symbol=symbol, error="empty statements"),
    )
    monkeypatch.setattr(sys, "argv", ["dcf-inputs", "--symbol", "zzz", "--json"])
    assert dcf_inputs.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["symbol"] == "ZZZ"
    assert payload["available"] is False
    assert payload["error"] == "empty statements"
