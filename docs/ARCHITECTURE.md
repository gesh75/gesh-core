# gesh-core — Architecture

> Interactive version: **[`architecture.html`](architecture.html)** (open in a browser).
> DCF methodology: **[`DCF.md`](DCF.md)**. Ledger: **[`LEDGER_PHASE4A.md`](LEDGER_PHASE4A.md)**.

`gesh-core` is the single source of truth for logic that the **engine**
(`gesh-project-trading`, port 9003) and the **product** (`Gesh-Project`, port 9000)
used to duplicate. A fix to a shared module now lands in both repos at once —
accidental drift is structurally impossible.

- **Install (dev):** `pip install -e ../gesh-core` from a consumer venv.
- **Install (pinned):** `pip install "gesh-core @ git+https://github.com/gesh75/gesh-core.git@<40-char-sha>"`
  — pin by commit SHA, never by floating tag. Latest **tag** is still `v0.6.1`;
  declared package version on `main` is **0.8.2**.
- **Deps:** numpy, yfinance, requests (pandas transitive). `praw` / `nltk` are
  optional (sentiment). Python ≥3.12.
- **CI:** GitHub Actions — ruff + mypy on 3.12; pytest + coverage on 3.12 / 3.13
  / 3.14. This tree has **329** `test_*` functions across 25 files. Import
  smoke is filesystem-driven (every non-vendored module). See [CI runbook](#ci-runbook).

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

## Shared modules (2026-08-31)

LOC is `wc -l` of the implementation file (or package, excluding vendored DCF).
Tests are in-repo `def test_*` counts for that area.

### Phase 3 extractions

| Module | Serves | LOC | Tests | Harmonization |
|---|---|---|---|---|
| `allocation_config` | both | 353 | 17 | cwd config (`GESH_CONFIG_PATH`); fail-closed `validate_action` |
| `ecg` | both | 179 | 12 | product-canonical (streak from equity *changes*) |
| `kelly` | both | 544 | 29 | union — engine 2y fetch + RH fallback + product `returns=` |
| `tax_harvester` | both | 328 | 16 | env-driven DB resolver; probe failure raises (no `/tmp`) |
| `db` | both | 347 | 12 | `connect()` + WAL + DDL + bounded history; calls `init_ledger_tables()` |
| `trading.contract` | both | 189 | 17 | `TradeIntent` + `source=` provenance + `len(symbol)≤12` |
| `trading.config` | both | 255 | 31 | strict safety booleans + engine-superset gates |
| `trading.state` | both | 550 | 19 | WAL + job_markers + two-book paper P&L |
| `trading.risk_gate_core` | both | 65 | 7 | shared `GateVerdict` + CASH_FLOOR math (rule #32) |
| `trading.levels` | engine | 199 | 15 | ATR-adaptive stops (3×ATR stop / 5×ATR target) |
| `trading.indicators` | engine | 46 | 4 | Wilder ATR helper; has direct tests as of 0.8.2 |

### Later extractions

| Module | Serves | LOC | Tests | Role |
|---|---|---|---|---|
| `db_path` | both | 51 | 5 | Single fail-closed SQLite resolver for `db` and `trading.state` |
| `market_fetch` | both | 168 | 13 | Yahoo retry + **explicit** Robinhood `fallback=` callable |
| `sentiment_connector` | both | 457 | 11 | praw → public JSON → ABSTAIN; VADER or keyword score |
| `trading.autopilot_core` | both | 80 | 6 | Pure fragments: entry floor, candidate marker, stop-sweep SELL |
| `gesh_core.dcf` | both¹ | 889 | 22 | Deterministic DCF — see [`DCF.md`](DCF.md) |
| `gesh_core.ledger` | both¹ | 1994 | 92 | Decision ledger Phase 4A/4B — see [`LEDGER_PHASE4A.md`](LEDGER_PHASE4A.md) |

¹ Extracted here for shared use. DCF is not wired into product :9000 or any gate.
Ledger has **no production caller in this repo**; host wiring is a consumer change.

## Database resolution — separate books by design

gesh-core cannot use `__file__` (it points inside the package). `db` and
`trading.state` both call `gesh_core.db_path.resolve_db_path()` so they cannot
silently point at different files.

| Module | Resolution |
|---|---|
| `trading.state`, `db` | `GESH_DB_PATH` → `cwd/gesh_financial.db`. Probe is a real DDL round-trip. **Failure raises** — there is no `/tmp` fallback (that used to split the audit trail from the daily-loss breaker). |
| `tax_harvester` | `GESH_TRACKER_DB` → `GESH_TRADING_HOME` → `cwd`. Same fail-closed probe; product may wire this to the engine DB. |
| `allocation_config` | `GESH_CONFIG_PATH` → `cwd/gesh_config.json` |

Each consumer keeps its **own** `gesh_financial.db` (rule #44). A cwd-resolved
path that did not exist logs a warning: the process may have been launched from
the wrong directory.

`connect()` sets `PRAGMA foreign_keys = ON` on every connection. `init_db()`
also creates the additive ledger tables.

## Public interfaces worth getting wrong

### Two different action vocabularies

| API | Allowed actions | Rejects |
|---|---|---|
| `allocation_config.validate_action` | `BUY`, `ADD`, `TRIM`, `SELL` (`TRADE_ACTIONS`) | non-`str`, unhashable payloads (`[]`, `{}`), lowercase / `HOLD` / whitespace |
| `trading.contract.TradeIntent` | `BUY`, `SELL`, `HOLD` | anything else; BUY/SELL also require `target_position_pct` |

`validate_action` returns `(False, "Invalid action — expected BUY, ADD, TRIM, or SELL")`
instead of raising `TypeError` on an unhashable `action` (PR #34). It does **not**
normalize case.

`auto_trade` defaults **False**. A truthy non-bool in `gesh_config.json` (`"yes"`,
`1`) cannot enable it — `_coerce_key` falls back to the safe default. `update_config`
raises `ValueError` on a type mismatch (write path fails fast).

### Strict safety booleans (`trading.config`)

`PAPER_MODE`, `REQUIRE_APPROVAL`, `MARKET_REGIME_GATE`:

| Input | Result |
|---|---|
| absent | conservative default (`True`) |
| `true` / `false` (any case, stripped) | accepted |
| blank, `1`/`0`, `yes`/`no`, anything else | `ConfigError` |

Both `load_risk_config()` and `effective_config()` fail closed. Raw env values
never appear in messages (`<missing>` / `<redacted>`). `resolved_at` is excluded
from `EffectiveConfig.__eq__` and from `config_hash`.

### Autopilot stop-sweep

`trading.autopilot_core.stop_sweep_intent` always sets `target_position_pct=0.0`.
A SELL without that field fails `TradeIntent.validate()` and the gate drops the
emergency exit.

### Market fetch fallback

`yf_download_with_retry(..., fallback=fn)` never imports a host module off
`sys.path`. The host must pass a trusted callable. Failures return `None`
(never raise). Three retries, exponential backoff on 401/crumb.

## Deliberately per-repo (by design — not drift)

| Module | Why |
|---|---|
| `trading.tracker` / `metrics` / `tracker_weekly` | Engine-only. Autonomy-gate source of truth (rules #26/#44). |
| `risk_gate.evaluate()` + time/PnL helpers | Deliberate per-repo gate policy (engine runs 3 extra gates); entangled with each repo's test seams. Shared math lives in `state` + `risk_gate_core`. |
| `consensus` | Two genuinely different engines (781 diff lines). See **[`CONSENSUS_CONVERGENCE.md`](CONSENSUS_CONVERGENCE.md)**. |

## CI runbook

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).
`permissions: contents: read`. Checkout does not persist credentials.

| Job | Python | What |
|---|---|---|
| `lint` | 3.12 | `ruff check src tests` then `mypy src` (vendored `dcf.vendor.*` ignored) |
| `test` | 3.12 / 3.13 / 3.14 | filesystem import of every non-vendored module, then `pytest --cov=gesh_core` |

Coverage is **informational** — there is no fail-under floor.

**File-descriptor limit (PR #46).** Buildkite's GitHub-Actions importer defaults
`ulimit -n` to 1024. pytest + sqlite fixtures + coverage on 3.13/3.14 then fail
with `EMFILE` ("too many open files"). The pytest step raises the soft limit to
65536 (or 10240) before invoking pytest. GitHub-hosted runners already have a
high limit; the `ulimit` is a no-op there.

Local equivalent:

```bash
pip install -e ".[dev]"
ruff check src tests
mypy src
ulimit -n 65536   # only needed on low-ulimit runners
pytest -q --cov=gesh_core --cov-report=term-missing
```

## Developer setup and pitfalls

```bash
# side-by-side under ~/Projects/, from the consumer venv
pip install -e ../gesh-core
pytest                    # from this repo
./docs/serve.sh           # http://127.0.0.1:8090/
```

- Launch servers / autopilot / the daily chain from the **repo root**, or set
  `GESH_DB_PATH` / `GESH_CONFIG_PATH`. A fresh empty book at the wrong cwd is a
  warning, not a redirect.
- Yahoo is required for Kelly fetch, ATR, DCF statements, and market_fetch.
  VPN/SNI blocks return empty/`None`/error dicts — they must not be patched
  with invented series.
- Sentiment works without Reddit OAuth (public JSON, rate-limited). `praw` +
  VADER improve quality when present; both missing → ABSTAIN / keyword score.
- Older HTML snapshots that still say “11 modules / 121 tests / VirtioFS →
  `/tmp`” are **wrong**. Current dashboards match this page.

## Verification status

- gesh-core CI green on `56f14d4e` (Actions run `33033241239`, 2026-08-27).
- **329** in-repo `test_*` functions at 0.8.2. Phase 3 consumer suite numbers
  (engine 293 / product 143) are a **2026-06-20** snapshot and were not re-run
  from this documentation pass.
- Extraction log: [`../PHASE3_STATUS.md`](../PHASE3_STATUS.md) (historical).
- Control document: [`../PROJECT_CONTROL.md`](../PROJECT_CONTROL.md).
