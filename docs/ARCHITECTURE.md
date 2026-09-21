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
  / 3.14. This tree has **426** `test_*` functions across 44 files. Import
  smoke is filesystem-driven (every non-vendored module). See [CI runbook](#ci-runbook).

`main` at this writing is `a6d287bb` (PR #88, 2026-09-21). Declared version is
still **0.8.2**; the fail-closed batch and precision overlay listed under
`CHANGELOG.md` **Unreleased** have already landed on `main`.

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

## Shared modules (2026-09-21)

LOC is `wc -l` of the implementation file (or package, excluding vendored DCF).
Tests are in-repo `def test_*` counts for that area.

### Phase 3 extractions

| Module | Serves | LOC | Tests | Harmonization |
|---|---|---|---|---|
| `allocation_config` | both | 535 | 35 | cwd config (`GESH_CONFIG_PATH`); `ActionCheck` + fail-closed `validate_action` |
| `ecg` | both | 179 | 12 | product-canonical (streak from equity *changes*) |
| `kelly` | both | 550 | 39 | union — engine 2y fetch + RH fallback + product `returns=` |
| `tax_harvester` | both | 328 | 16 | env-driven DB resolver; probe failure raises (no `/tmp`) |
| `db` | both | 347 | 12 | `connect()` + WAL + DDL + bounded history; calls `init_ledger_tables()` |
| `trading.contract` | both | 194 | 22 | `TradeIntent` + `source=` provenance + `len(symbol)≤12` |
| `trading.config` | both | 375 | 53 | strict safety booleans + `NUMERIC_SPECS` (PR #79) |
| `trading.state` | both | 565 | 27 | WAL + job_markers + two-book paper P&L + `LedgerUnavailable` |
| `trading.risk_gate_core` | both | 65 | 8 | shared `GateVerdict` + CASH_FLOOR math (rule #32) |
| `trading.levels` | engine | 199 | 15 | ATR-adaptive stops (3×ATR stop / 5×ATR target) |
| `trading.indicators` | engine | 46 | 4 | Wilder ATR helper; has direct tests as of 0.8.2 |

### Later extractions

| Module | Serves | LOC | Tests | Role |
|---|---|---|---|---|
| `db_path` | both | 76 | 14 | Path-only resolver + explicit `ensure_db_writable` bootstrap (PR #81) |
| `market_fetch` | both | 168 | 13 | Yahoo retry + **explicit** Robinhood `fallback=` callable |
| `sentiment_connector` | both | 457 | 11 | praw → public JSON → ABSTAIN; VADER or keyword score |
| `trading.autopilot_core` | both | 165 | 30 | Entry floor, candidate marker, stop-sweep SELL, **precision overlay** (PR #88) |
| `gesh_core.dcf` | both¹ | 889 | 22 | Deterministic DCF — see [`DCF.md`](DCF.md) |
| `gesh_core.ledger` | both¹ | 1994 | 92 | Decision ledger Phase 4A/4B — see [`LEDGER_PHASE4A.md`](LEDGER_PHASE4A.md) |

¹ Extracted here for shared use. DCF is not wired into product :9000 or any gate.
Ledger has **no production caller in this repo**; host wiring is a consumer change.

## Database resolution — separate books by design

gesh-core cannot use `__file__` (it points inside the package). `db` and
`trading.state` both call `gesh_core.db_path.resolve_db_path()` so they cannot
silently point at different files.

**R7 (PR #81):** `resolve_db_path()` is I/O-free — it does not mkdir, connect, or
CREATE/DROP. Importing `gesh_core.db` or `trading.state` against a read-only
operational sentinel must not mutate it. Writability is an explicit bootstrap:
`ensure_db_writable` (called from first `connect` / `_conn` / `init_db`). The
probe is a real DDL round-trip because VirtioFS (macOS shared mount) cannot do
SQLite DDL/WAL from a sandbox. **Failure raises** — there is no `/tmp` fallback
(that used to split the audit trail from the daily-loss breaker).

| Module | Resolution |
|---|---|
| `trading.state`, `db`, `ledger` | `GESH_DB_PATH` → `cwd/gesh_financial.db`. Path at import; probe on first connect. |
| `tax_harvester` | `GESH_TRACKER_DB` → `GESH_TRADING_HOME` → `cwd`. Own fail-closed probe; product may wire this to the engine DB. |
| `allocation_config` | `GESH_CONFIG_PATH` → `cwd/gesh_config.json` |

Each consumer keeps its **own** `gesh_financial.db` (rule #44). A cwd-resolved
path that did not exist logs a warning: the process may have been launched from
the wrong directory.

`connect()` sets `PRAGMA foreign_keys = ON` on every connection. `init_db()`
also creates the additive ledger tables.

Pytest collection (`tests/conftest.py`) sets `GESH_DB_PATH` to a temp file and
blocks `socket.connect` so imports cannot touch the checkout book or the
network. The temp root is removed in `pytest_unconfigure`.

## Public interfaces worth getting wrong

### Two different action vocabularies

| API | Allowed actions | Rejects |
|---|---|---|
| `allocation_config.validate_action` | `BUY`, `ADD`, `TRIM`, `SELL` (`TRADE_ACTIONS`) | non-`str`, unhashable payloads (`[]`, `{}`), lowercase / `HOLD` / whitespace |
| `trading.contract.TradeIntent` | `BUY`, `SELL`, `HOLD` | anything else; BUY/SELL also require `target_position_pct` |

`validate_action` returns `ActionCheck` (unpackable as `ok, reason = …`) instead
of raising `TypeError` on an unhashable `action` (PR #34). Match `code`, not
free-text reasons, in new callers. It does **not** normalize case.

### Allocation permission split (PR #77)

Financial limits (size, open positions, cash floor, scanner price) **always**
run. Live-execution permission (`auto_trade`) is a last check. Paper callers
pass `require_live_permission=False` to skip only that permission.

```python
from gesh_core.allocation_config import validate_action

check = validate_action("BUY", "NVDA", 3500, open_positions=2, current_cash=6000)
# check.ok, check.reason, check.code
# paper / recommendation path:
check = validate_action(
    "BUY", "NVDA", 3500, 2, current_cash=6000, require_live_permission=False
)
```

`auto_trade` defaults **False**. A truthy non-bool in `gesh_config.json`
(`"yes"`, `1`) cannot enable it — `_coerce_key` falls back to the safe default.
`update_config` raises `ValueError` on a type mismatch (write path fails fast).
`load_config` degrades per-key on a **boolean/string** type mismatch, but
**numeric** caps that are present-but-invalid (wrong type, NaN, infinity,
negative, non-integer counts) raise `ConfigError` (PR #79). A corrupt file
degrades to defaults and is left on disk.

`allocation_config.DEFAULT_CONFIG["paper_mode"]` defaults **False** (routes to
`paper_trades` when True). That is **not** `trading.config.PAPER_MODE`, which
defaults **True**. Do not treat them as one switch.

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

### Numeric safety (`NUMERIC_SPECS`, PR #79)

Risk-config numbers and Kelly unit-interval caps (`KELLY_MAX_POSITION_PCT`,
`KELLY_MAX_GROSS_PCT`) use `gesh_core.trading.config._parse_numeric` /
`parse_unit_interval`. They no longer silently fall back on malformed tokens.

| Input | Result |
|---|---|
| absent / blank | documented default |
| finite value in range | accepted |
| NaN, infinity, non-numeric, out of range | `ConfigError` |
| `0` | valid only where `allow_zero=True` (`MAX_POSITION_PCT`, `MIN_CASH_BUFFER_USD`, `MIN_ENTRY_SCORE`, …). `MAX_DAILY_LOSS_PCT`, `MAX_ORDERS_PER_DAY`, `PAPER_CASH_USD` reject zero |

Cross-key rules: `MIN_CONFIDENCE_RISK_OFF` cannot be below `MIN_CONFIDENCE`;
`MAX_PRICE_AGE_SECONDS_PAPER` cannot be below `MAX_PRICE_AGE_SECONDS`.
`effective_config().config_hash` includes these numeric limits and their
provenance.

String knobs (`MARKET_OPEN_HHMM`, `KILL_SWITCH_PATH`, …) still use `os.getenv`
— a set-but-empty value is kept as `""`, not the default.

### Precision overlay (PR #88)

`trading.autopilot_core.precision_overlay_blocks(action, row) -> OverlayDecision`
is a **second-stage BUY veto** after consensus. Pure. No I/O.

Vetoes BUY when votes are present:

1. `Rel.Strength == -1` (even on STRONG BUY)
2. Price confirmation failed: neither `Momentum` nor `Trend` is `+1`, when
   either node is in `votes`
3. Net bullish votes (`bullish - bearish`) `< 2`, or `bearish > bullish`
4. `Macro == -1` unless verdict is `STRONG BUY` **and** `Rel.Strength == 1`

SELL / HOLD are never blocked. Missing / empty / non-dict `votes` **fail open**
(the score floor still applies). Disabled when `PRECISION_OVERLAY` is `0`,
`false`, or `off` (case-insensitive after strip). Default is on (`"1"`).

```python
from gesh_core.trading.autopilot_core import precision_overlay_blocks

d = precision_overlay_blocks("BUY", {"verdict": "BUY", "votes": {"Rel.Strength": 1, "Momentum": 1, "Macro": 1}})
# d.blocked, d.reason
```

### Entry floor and stop-sweep

`entry_floor_blocks(action, raw_score, min_entry_score)` gates **BUY** only.
SELL is never floored. Non-finite `raw_score` / `min_entry_score` fail closed
(PR #64) — `NaN < floor` is `False` in IEEE-754 and would otherwise admit a
missing consensus number as a new long.

`stop_sweep_intent` always sets `target_position_pct=0.0`. A SELL without that
field fails `TradeIntent.validate()` and the gate drops the emergency exit.

`TradeIntent.validate` rejects non-finite stop / take-profit the same as
non-positive levels (PR #64).

### Paper daily-loss book (`LedgerUnavailable`, PR #78)

`trading.state.paper_realized_pnl_usd_today()` sums **both** paper books in
this DB (`paper_outcomes` and `paper_trades`). One missing table is expected
(two-book design) and is skipped. An empty present table is a measured flat
day. If **neither** table is readable, it raises `LedgerUnavailable` — that is
not a fabricated `$0` day.

The sum is still **UTC-day** (`00:00 UTC`). `count_orders_today` is **ET-day**.
Those clocks disagree for the last hours of the ET session (known; draft PR
#56). Do not assume they share a calendar day.

### Market fetch fallback

`yf_download_with_retry(..., fallback=fn)` never imports a host module off
`sys.path`. The host must pass a trusted callable. Failures return `None`
(never raise). Three retries; exponential backoff on 401/crumb (`base * 2^attempt`).

### Kelly sizing (call-time vs import-time)

`kelly._max_position_pct()` re-reads `KELLY_MAX_POSITION_PCT` at **call** time
via `parse_unit_interval` (invalid input **raises**, it does not fall back).
The module constant `kelly.MAX_POSITION_PCT` is fixed at **import** time —
long-lived servers that only read the constant will miss a later env change.
Gross-exposure is the same parser. Correlation, cost, and autocorr knobs are
call-time and still fall back on malformed tokens.

`_max_drawdown` includes starting equity as the first peak (PR #80). A −10%
first return then flat is −10%, not 0.

### Tax wash-sale window

`WASH_SALE_DAYS = 30`. `get_wash_status` treats the window as open while
`wash_safe_date > today` (string ISO compare). Harvest math is `Decimal`
quantized to cents. Draft PR #68 would keep day 30 closed — **not on `main`**.

## Environment variables

Parsers differ. Do not assume `1`/`0`/`yes` work everywhere.

| Family | Variables | Behavior |
|---|---|---|
| **Strict bool** | `PAPER_MODE`, `REQUIRE_APPROVAL`, `MARKET_REGIME_GATE` | absent → `True`; `true`/`false` only; blank/other → `ConfigError` |
| **Numeric specs** | `MAX_POSITION_PCT`, `MAX_DAILY_LOSS_PCT`, `MAX_ORDERS_PER_DAY`, `MIN_CASH_BUFFER_USD`, `MIN_CONFIDENCE`, `MIN_ENTRY_SCORE`, `PAPER_CASH_USD`, `MAX_PRICE_AGE_SECONDS` / `_PAPER`, `MAX_SECTOR_PCT`, `EARNINGS_PROXIMITY_HOURS`, `MAX_CONSECUTIVE_LOSS_DAYS`, `MIN_CONFIDENCE_RISK_OFF`, `MARKET_REGIME_MA_DAYS`, `KELLY_MAX_POSITION_PCT`, `KELLY_MAX_GROSS_PCT` | empty → default; NaN / inf / malformed / OOR → `ConfigError` |
| **String getenv** | `KILL_SWITCH_PATH`, `MARKET_OPEN_HHMM`, `MARKET_CLOSE_HHMM`, `MARKET_TIMEZONE`, `GESH_DB_PATH`, `GESH_CONFIG_PATH`, `GESH_TRACKER_DB`, `GESH_TRADING_HOME` | set-but-empty is kept as `""` (path vars then resolve to cwd defaults when unset, not when blank) |
| **Loose disable** | `PRECISION_OVERLAY` (`0`/`false`/`off`, lowercased); `EQUITY_USE_ATR_STOPS` and `KELLY_AUTOCORR_SHRINK` (`0`/`false`/`False` only) | default **on** |
| **Fallback float** | `KELLY_CORR_THRESHOLD`, `KELLY_COST_BPS`, `KELLY_REBALANCE_DAYS` | malformed → default (not the numeric-spec family) |
| **Import-time crash** | `EQUITY_ATR_PERIOD`, `EQUITY_ATR_STOP_MULT`, `EQUITY_MIN_STOP_PCT`, `EQUITY_MAX_STOP_PCT`, `EQUITY_ATR_TARGET_MULT` | `int()` / `float()` at import; blank `EQUITY_ATR_PERIOD=""` raises `ValueError` |
| **Import-time string** | `GESH_SENTIMENT_CACHE`, `REDDIT_CLIENT_ID` / `_SECRET` / `_USER_AGENT` | captured at import (cwd `.env` first, then `os.environ`) |

| Variable | Module | When read | Default / notes |
|---|---|---|---|
| `GESH_DB_PATH` | `db_path` | call (path); import binds `DB_PATH` | else `cwd/gesh_financial.db` |
| `GESH_TRACKER_DB` | `tax_harvester` | call | wash-sale book; else `GESH_TRADING_HOME` / cwd |
| `GESH_TRADING_HOME` | `tax_harvester` | call | `<home>/gesh_financial.db` |
| `GESH_CONFIG_PATH` | `allocation_config` | call | else `cwd/gesh_config.json` |
| `GESH_SENTIMENT_CACHE` | `sentiment_connector` | **import** | else `cwd/.sentiment_cache.json` |
| `REDDIT_CLIENT_ID` / `_SECRET` / `_USER_AGENT` | `sentiment_connector` | **import** | cwd `.env` first, then `os.environ` |
| `PRECISION_OVERLAY` | `autopilot_core` | call | default on; `0`/`false`/`off` disables overlay |
| `PAPER_MODE` / `REQUIRE_APPROVAL` / `MARKET_REGIME_GATE` | `trading.config` | call | **strict** `true`/`false` only |
| `KILL_SWITCH_PATH` | `trading.config` | call | default `~/.gesh/KILL` |
| `MIN_ENTRY_SCORE` | `trading.config` | call | `0.35` BUY raw_score floor; `0.0` disables |
| `PAPER_CASH_USD` | `trading.config` | call | `100000` (CASH_FLOOR in paper); zero rejected |
| `KELLY_MAX_POSITION_PCT` | `kelly` | call *and* import | `[0, 1]`; default `0.25`; invalid **raises** |
| `KELLY_MAX_GROSS_PCT` | `kelly` | call | default `1.0`; invalid **raises** |
| `KELLY_CORR_THRESHOLD` | `kelly` | call | default `0.70`; malformed → default |
| `KELLY_COST_BPS` / `KELLY_REBALANCE_DAYS` | `kelly` | call | 10 bps / 21 days; malformed → default |
| `KELLY_AUTOCORR_SHRINK` | `kelly` | call | `0`/`false`/`False` disables; default on |
| `EQUITY_USE_ATR_STOPS` | `trading.levels` | **import** | loose disable; default on |
| `EQUITY_ATR_PERIOD` / `_STOP_MULT` / `_TARGET_MULT` | `trading.levels` | **import** | `14` / `3.0` / `5.0`; **crash on blank** |
| `EQUITY_MIN_STOP_PCT` / `EQUITY_MAX_STOP_PCT` | `trading.levels` | **import** | `0.03` / `0.15` |

DCF CLI flags (`--terminal-growth`, `--risk-free`) are not environment variables.

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

Coverage is **informational** — there is no fail-under floor. CI installs
`.[test]` for pytest; lint installs `ruff` + `mypy` separately. Local extras:
`.[test]` = pytest + coverage; `.[dev]` = those plus ruff + mypy.

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

Latest green `main` CI: Actions run `35547132758` on `a6d287bb` (PR #88 merge).

## Developer setup and pitfalls

```bash
# side-by-side under ~/Projects/, from the consumer venv
pip install -e ../gesh-core
pytest                    # from this repo
./docs/serve.sh           # http://127.0.0.1:8090/
```

- Launch servers / autopilot / the daily chain from the **repo root**, or set
  `GESH_DB_PATH` / `GESH_CONFIG_PATH`. A fresh empty book at the wrong cwd is a
  warning, not a redirect. `resolve_db_path` will not create that file; the
  first `connect` will.
- `NaN > cap` is `False` in IEEE-754. Size, cash, score, and stop checks must
  use `math.isfinite` — the fail-closed batch (PRs #64, #77–#79) exists because
  they did not.
- Yahoo is required for Kelly fetch, ATR, DCF statements, and market_fetch.
  VPN/SNI blocks return empty/`None`/error dicts — they must not be patched
  with invented series.
- Sentiment works without Reddit OAuth (public JSON, rate-limited). `praw` +
  VADER improve quality when present; both missing → ABSTAIN / keyword score.
  Reddit keys and `GESH_SENTIMENT_CACHE` are captured at **import**.
- `EQUITY_*` ATR knobs are import-time and use a loose / crashy parser — not
  the safety-boolean or `NUMERIC_SPECS` contract. A blank `EQUITY_ATR_PERIOD=""`
  raises `ValueError` at import. Draft PR #70 (empty ATR env) is **not on
  `main`**.
- `PRECISION_OVERLAY` is a loose disable flag. It is **not** a strict safety
  boolean — `1`/`0` work here; they do **not** work for `PAPER_MODE`.
- Older HTML snapshots that still say “11 modules / 121 tests / VirtioFS →
  `/tmp`” are **wrong**. Current dashboards match this page.

## Verification status

- gesh-core CI green on `a6d287bb` (Actions run `35547132758`, 2026-09-21).
  Latest tag remains `v0.6.1`; GitHub Releases list is empty. Pin by SHA.
- **426** in-repo `test_*` functions across 44 files. Phase 3 consumer suite
  numbers (engine 293 / product 143) are a **2026-06-20** snapshot and were
  not re-run from this documentation pass.
- Extraction log: [`../PHASE3_STATUS.md`](../PHASE3_STATUS.md) (historical).
- Control document: [`../PROJECT_CONTROL.md`](../PROJECT_CONTROL.md).
- Gap scan (historical, SHA `56f14d4`): [`../GAP_ANALYSIS.md`](../GAP_ANALYSIS.md).
