# Consensus Convergence — Proposal & Plan

> Interactive dashboard: **[`consensus-comparison.html`](consensus-comparison.html)**.
>
> **Status: PROPOSAL.** `consensus` is correctly kept per-repo *today*. This document is the
> code-verified analysis + staged plan for *if/when* you decide to converge. The live code
> cutover changes customer-facing dashboard signals, so it proceeds **only on explicit sign-off**.

## Why consensus is per-repo

The engine (`gesh-project-trading/consensus.py`, 844 LOC) and product
(`gesh-project/consensus.py`, 487 LOC) are **two genuinely different engines** — 781 diff
lines. This is intentional divergence, not accidental drift:

| | Engine | Product |
|---|---|---|
| Nodes | **11** (incl. live Reddit News + FRED Macro) | **9** voting (no live Reddit, no Macro) |
| Weights | dynamic `_regime_weights` (4 backtest-validated profiles) | static `NODE_WEIGHTS` dict |
| Fetch | once → slice arrays to nodes (~3 calls/symbol) | each node self-fetches (~8 calls/holding) |
| Fetch infra | `_yf_download_with_retry` + Robinhood fallback | `price_source.yf_download` delegate |
| Fundamentals/Analyst | OpenBB → yfinance → **RH tertiary** | OpenBB → yfinance |
| Role | autonomy-gate **signal source of truth** | customer **dashboard** |

**Shared:** vote scheme (BULLISH +1 / NEUTRAL 0 / BEARISH −1 / ABSTAIN), verdict thresholds
(≥0.55 STRONG BUY, ≥0.25 BUY, min 4 active nodes), the weighted-tally formula, the
`(vote, detail)` node contract, OpenBB→yfinance fallback, FFT/Kelly excluded from the vote,
ThreadPoolExecutor portfolio runs, ABSTAIN-on-error.

## Recommendation

**Phased full convergence** — the product adopts the engine's 11-node architecture, in 7 stages
over ~8 weeks, with latency wins first and customer-visible changes later behind validation.

**Why converge:** the engine is the proven system (regime weights validated across 6 assets /
24 months; live Reddit + Macro; fetch-once cuts ~75% of yfinance calls and avoids rate-limit
thrashing at scale). Static weights + a 9-node set handicap product signal quality, and three
connectors (`sentiment_connector`, `macro_connector`, `fundamentals_openbb`) are already
duplicated. **Risk of changing: medium** (verdicts shift on new nodes — explained + staged).
**Risk of not changing: high** (drift + signal-quality gap widen).

## Staged plan

| Phase | Weeks | Work | Acceptance gate |
|---|---|---|---|
| **1 · Dependency & infra ✅ DONE (2026-06-21)** | 1–2 | Shared fetch infra extracted to **`gesh_core.market_fetch`** (`yf_download_with_retry` + `fetch_ohlcv` + `fetch_spy_close`, retry + RH fallback + 30-min SPY cache) instead of copy-pasting into product. 8 tests. | ✅ product imports market_fetch + macro_connector + fundamentals_openbb cleanly; `fetch_ohlcv` returns 252d w/ retry. `sentiment_connector` deferred to Phase 5 (live-Reddit dep). |
| **2 · Node signatures ✅ DONE (2026-06-21)** | 2–3 | node_relative_strength gained optional arrays (the last self-fetching OHLCV node); momentum/trend/volume already had them. Behavior-preserved. +6 tests. | ✅ all OHLCV nodes accept arrays; default call unchanged → verdicts identical. Merged to product main. |
| **3 · Pre-fetch & slicing ✅ DONE (2026-06-21)** | 3–4 | run_consensus_holding already pre-fetched 252d once; wired Rel.Strength to that sym close + a 30-min-cached SPY (gesh_core.market_fetch.fetch_spy_close), dropping the last [symbol,SPY] self-fetch. +2 tests. | ✅ last redundant fetch removed; RS now uses the engine's 22-bar window (**verdict-affecting** — first customer-signal change, live on product main). |
| **4 · Regime weights ✅ DONE (2026-06-21, branch)** | 4–5 | Ported `_regime_weights(symbol)` into product: detect_regimes (30-min cache) re-weights Trend/Momentum/Fundamentals per regime (BREAKOUT-READY/TRENDING/RANGING), base fallback. +9 tests. | ✅ engine-parity profiles; deterministic in tests. On `feat/consensus-convergence-phase4` (verdict-affecting — awaiting review/merge). |
| **5 · Live Reddit + Macro ✅ DONE (2026-06-21, branch)** | 5–6 | sentiment_connector extracted to gesh-core (shared, +7 tests); product node_news now tries live Reddit → cached-DB fallback. Macro node already existed in product. +3 tests. | ✅ live crowd sentiment when available, graceful DB/ABSTAIN fallback. On `feat/consensus-convergence-phase5` (verdict-affecting). engine shim on main (293✓), gesh-core v0.3.0. |
| 6 · Testing & validation | 6–7 | Mock-array unit tests; 20-symbol parity vs engine | verdicts match engine ±0.05 raw_score |
| 7 · Dashboard & deploy | 7–8 | Macro card + regime/weights UI; profile + staged rollout | all 11 nodes render; <15s / 10 holdings |

## Risks to manage

- **Customer verdicts shift** — Macro (bearish on inverted curve / high VIX) + live Reddit can
  flip historical signals. Stage + explain in the UI.
- **Macro dependency** — `fredapi` / API key absent → Macro ABSTAINs, confidence drops.
- **Reddit connector** — `praw` + `nltk` + credentials; must fall back to cached DB.
- **Cache TTL misalignment** — `_SPY_CACHE` / `_REGIME_LABEL_CACHE` shared keys, different TTLs.
- **ECG signature mismatch** — engine `_compute_drawdown_from_peak`/`_loss_streak`/`_classify`
  vs product `_drawdown`/`_streak`/`_gate_status`.
- **Confidence denominator** — `active_nodes / len(NODE_WEIGHTS)` moves 9 → 11; ensure parity.
- **Regime/ fetch latency & timestamp delta** — cache aggressively; accept ±0.02 raw_score.

## Decision

Keep per-repo until you greenlight Phase 1. This plan makes convergence a controlled, reversible,
acceptance-gated project — not a silent merge of the alpha engine.
