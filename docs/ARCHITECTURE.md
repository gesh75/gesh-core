# gesh-core — Architecture

> Interactive version: **[`architecture.html`](architecture.html)** (open in a browser).

`gesh-core` is the single source of truth for logic that the **engine**
(`gesh-project-trading`, port 9003) and the **product** (`gesh-project`, port 9000)
used to duplicate. A fix to a shared module now lands in both repos at once —
accidental drift is structurally impossible.

- **Install:** `pip install "gesh-core @ git+https://github.com/gesh75/gesh-core.git@v0.1.0"`
  (dev: `pip install -e ../gesh-core`)
- **Deps:** numpy + yfinance (pandas transitive). Python ≥3.12.
- **CI:** GitHub Actions, green on 3.12 / 3.13 / 3.14 — installs the package, imports
  every module, runs 121 tests.

## The shim pattern

Each consumer repo keeps a thin stub where the module used to live. It rebinds
`sys.modules`, so `import db` returns the gesh-core module itself — preserving every
import form **and** test monkeypatching:

```python
# gesh-project-trading/db.py  (identical stub in gesh-project)
import sys
from gesh_core import db as _impl
sys.modules[__name__] = _impl     # import db  →  the single gesh_core.db
```

This is why `from trading.config import RiskConfig`, `import db as dbmod`, underscore
names, and `monkeypatch.setattr(db, "DB_PATH", tmp)` all keep working unchanged.

## The 11 shared modules

| Module | Serves | LOC | Tests | Harmonization |
|---|---|---|---|---|
| `allocation_config` | both | 282 | 7 | identical → cwd config (`GESH_CONFIG_PATH`) |
| `ecg` | both | 158 | 10 | product-canonical (streak from equity *changes*) |
| `kelly` | both | 238 | 13 | union — engine 2y fetch + RH fallback + product `returns=` |
| `tax_harvester` | both | 278 | 13 | env-driven DB resolver |
| `db` | both | 298 | 9 | union — `connect()`+WAL+DDL + corruption-tolerant history |
| `trading.contract` | both | 151 | 13 | union — `source=` provenance + `len(symbol)≤12` cap |
| `trading.config` | both | 114 | 9 | engine-superset gates + product robust env parsing |
| `trading.state` | both | 327 | 10 | union — WAL + job_markers + two-book paper P&L |
| `trading.risk_gate_core` | both | 65 | 7 | shared `GateVerdict` + CASH_FLOOR math (rule #32) |
| `trading.levels` | engine | 203 | 7 | pure — ATR-adaptive stops |
| `trading.indicators` | engine | 46 | 0¹ | pure — ATR helper, dependency of `levels` |

¹ exercised through `levels`' tests + engine's `test_atr_stops`.

## Database resolution — separate books by design

gesh-core can't use `__file__` (it points inside the package), so DB paths resolve at
**call time**. Each repo keeps its **own** `gesh_financial.db` (rule #44 — engine and
product paper books are deliberately separate); only the wash-sale tracker is wired
cross-repo.

| Module | Resolution |
|---|---|
| `trading.state`, `db` | `GESH_DB_PATH` → `cwd/gesh_financial.db` (VirtioFS → `/tmp` fallback) |
| `tax_harvester` | `GESH_TRACKER_DB` → `GESH_TRADING_HOME` → `cwd` (product wires → engine DB) |
| `allocation_config` | `GESH_CONFIG_PATH` → `cwd/gesh_config.json` |

## Deliberately per-repo (by design — not drift)

| Module | Why |
|---|---|
| `trading.tracker` / `metrics` / `tracker_weekly` | Engine-only. Autonomy-gate source of truth (rules #26/#44). |
| `risk_gate.evaluate()` + time/PnL helpers | Deliberate per-repo gate policy (engine runs 3 extra gates); entangled with each repo's test seams. Shared math lives in `state` + `risk_gate_core`. |
| `consensus` | Two genuinely different engines (781 diff lines). See **[`CONSENSUS_CONVERGENCE.md`](CONSENSUS_CONVERGENCE.md)**. |

## Verification status

- Engine suite **293 passed**, product **143 passed** (+7 pre-existing), gesh-core
  **121 passed** — across every extraction, zero regressions.
- Full phase-by-phase record: [`../PHASE3_STATUS.md`](../PHASE3_STATUS.md).
