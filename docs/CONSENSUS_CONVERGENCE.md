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
| 1 · Dependency & infra | 1–2 | Port retry fetch + RH fallback + TTL caches; verify connectors import | connectors import; `_fetch_ohlcv` returns 252d w/ retry |
| 2 · Node signatures | 2–3 | Nodes accept optional pre-fetched arrays, self-fetch as fallback | all 11 nodes accept arrays; no-arg call still works |
| 3 · Pre-fetch & slicing | 3–4 | Fetch 252d + spy_close ONCE, slice to nodes | 1 download/symbol; ~75% fewer calls |
| 4 · Regime weights | 4–5 | Port `_regime_weights` + `detect_regimes` (30min cache) | weights adjust per regime, validated vs engine |
| 5 · Live Reddit + Macro | 5–6 | Live Reddit News (DB fallback); add `node_macro` as Node 11 | News live when available; Macro participates / ABSTAINs cleanly |
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
