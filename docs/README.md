# gesh-core docs

| Doc | What |
|---|---|
| **[architecture.html](architecture.html)** | Interactive architecture dashboard — module map, shim pattern, DB resolution, deferred set. Open in a browser. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Same, as markdown (current as of `a6d287bb` / 0.8.2 + Unreleased). |
| [DCF.md](DCF.md) | Deterministic DCF API, methodology, refusals, CLI. |
| **[consensus-comparison.html](consensus-comparison.html)** | Engine 11-node vs product 9-node dashboard + the staged convergence roadmap. |
| [CONSENSUS_CONVERGENCE.md](CONSENSUS_CONVERGENCE.md) | Consensus convergence proposal + plan (markdown). |
| [LEDGER_PHASE4A.md](LEDGER_PHASE4A.md) | Decision-ledger schema, hash contracts, tenant isolation. |
| [../PHASE3_STATUS.md](../PHASE3_STATUS.md) | Phase-by-phase extraction log (complete 2026-06-20). |
| [../PROJECT_CONTROL.md](../PROJECT_CONTROL.md) | Canonical control: pins, blockers, next action. |
| [../CHANGELOG.md](../CHANGELOG.md) | Version history. |

The HTML dashboards are single self-contained files (one Google-Fonts link) in the GESH dark
theme. **Kept local / private — not published** (gesh-core holds internal trading IP).

### View locally

```bash
./docs/serve.sh          # → http://127.0.0.1:8090/   (landing → both dashboards)
./docs/serve.sh 9001     # custom port
```

Or just open `docs/index.html` in a browser directly.
