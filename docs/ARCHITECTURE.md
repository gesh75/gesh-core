# gesh-core — Architecture

> Interactive version: **[`architecture.html`](architecture.html)** (open in a browser).

`gesh-core` is the single source of truth for logic that the **engine**
(`gesh-project-trading`, port 9003) and the **product** (`Gesh-Project`, port 9000)
used to duplicate. A fix to a shared module now lands in both repos at once —
accidental drift is structurally impossible.

- **Install:** `pip install "gesh-core @ git+https://github.com/gesh75/gesh-core.git@<40-char-sha>"`
  (dev: `pip install -e ../gesh-core`). **Never pin a tag** — `v0.6.1` is the
  latest tag and is many commits behind `main`.
- **Deps:** numpy + yfinance + requests (pandas transitive). Python ≥3.12.
  praw / nltk are optional (sentiment degrades to Reddit JSON + keywords).
- **CI:** GitHub Actions, green on 3.12 / 3.13 / 3.14 — installs the package,
  imports every non-vendored module (filesystem discovery), runs pytest + ruff + mypy.

## The shim pattern

Each consumer repo keeps a thin stub where the module used to live. It rebinds
`sys.modules`, so `import db` returns the gesh-core module itself — preserving every
import form **and** test monkeypatching:

```python
# gesh-project-trading/db.py  (identical stub in Gesh-Project)
import sys
from gesh_core import db as _impl
sys.modules[__name__] = _impl     # import db  →  the single gesh_core.db
```

This is why `from trading.config import RiskConfig`, `import db as dbmod`, underscore
names, and `monkeypatch.setattr(db, "DB_PATH", tmp)` all keep working unchanged.

## Shared modules (2026-08-22)

Phase 3 extracted the accidental-drift set. Phase 4A added the decision ledger.
v0.7–0.8 added deterministic DCF. LOC is source-only, excluding `dcf/vendor`.

| Module | Serves | Notes |
|---|---|---|
| `allocation_config` | both | cwd config (`GESH_CONFIG_PATH`); fail-closed actions |
| `ecg` | both | product-canonical (streak from equity *changes*) |
| `kelly` | both | engine 2y fetch + RH fallback + product `returns=` |
| `tax_harvester` | both | env-driven DB resolver; no `/tmp` fallback |
| `db` / `db_path` | both | WAL+DDL + corruption-tolerant history; shared path resolver |
| `market_fetch` | both | retry-hardened Yahoo + injected RH fallback |
| `sentiment_connector` | both | praw optional; JSON API + keyword fallback |
| `trading.contract` | both | `source=` provenance + `len(symbol)≤12` |
| `trading.config` | both | strict safety booleans; engine-superset gates |
| `trading.state` | both | WAL + job_markers + two-book paper P&L |
| `trading.risk_gate_core` | both | `GateVerdict` + CASH_FLOOR math (rule #32) |
| `trading.levels` | engine | ATR-adaptive stops |
| `trading.indicators` | engine | Wilder ATR; now has direct tests |
| `trading.autopilot_core` | both | entry floor, candidate marker, stop-sweep intent |
| `dcf` | both | deterministic fair value; measurement-only (rule #47) |
| `ledger` | both | content-addressed snapshots, tenant isolation |

## Database resolution — separate books by design

gesh-core can't use `__file__` (it points inside the package), so DB paths resolve at
**call time**. Each repo keeps its **own** `gesh_financial.db` (rule #44 — engine and
product paper books are deliberately separate); only the wash-sale tracker is wired
cross-repo.

| Module | Resolution |
|---|---|
| `trading.state`, `db` | `GESH_DB_PATH` → `cwd/gesh_financial.db` |
| `tax_harvester` | `GESH_TRACKER_DB` → `GESH_TRADING_HOME` → `cwd` (product wires → engine DB) |
| `allocation_config` | `GESH_CONFIG_PATH` → `cwd/gesh_config.json` |

## Deliberately per-repo (by design — not drift)

| Module | Why |
|---|---|
| `trading.tracker` / `metrics` / `tracker_weekly` | Engine-only. Autonomy-gate source of truth (rules #26/#44). |
| `risk_gate.evaluate()` + time/PnL helpers | Deliberate per-repo gate policy (engine runs 3 extra gates); entangled with each repo's test seams. Shared math lives in `state` + `risk_gate_core`. |
| `consensus` | Two genuinely different engines (781 diff lines). See **[`CONSENSUS_CONVERGENCE.md`](CONSENSUS_CONVERGENCE.md)**. |

## Verification status

- gesh-core CI green on `97a519b7` (Actions run `31493540985`) before the 0.8.2
  revision; 0.8.2 adds DCF characterization tests and filesystem-driven imports.
- Full phase-by-phase record: [`../PHASE3_STATUS.md`](../PHASE3_STATUS.md).
- Control document: [`../PROJECT_CONTROL.md`](../PROJECT_CONTROL.md).
