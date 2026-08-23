# gesh-core docs

| Doc | What |
|---|---|
| **[architecture.html](architecture.html)** | Interactive architecture dashboard — module map, shim pattern, DB resolution, deferred set. Open in a browser. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Same inventory as markdown, plus public-interface contracts and developer pitfalls. |
| **[DCF.md](DCF.md)** | Deterministic DCF (0.8.x): fetched vs assumed, refusal guards, CLI, vendor policy. |
| [LEDGER_PHASE4A.md](LEDGER_PHASE4A.md) | Decision ledger Phase 4A/4B — hashes, tenant isolation, recording orchestration. |
| **[consensus-comparison.html](consensus-comparison.html)** | Engine 11-node vs product 9-node dashboard + the staged convergence roadmap. |
| [CONSENSUS_CONVERGENCE.md](CONSENSUS_CONVERGENCE.md) | Consensus convergence proposal + plan (markdown). |
| [../PHASE3_STATUS.md](../PHASE3_STATUS.md) | Phase-by-phase extraction log (2026-06 snapshot). |
| [../PROJECT_CONTROL.md](../PROJECT_CONTROL.md) | Pins, safety-boolean contract, blockers. |

The HTML dashboards are single self-contained files (one Google-Fonts link) in the GESH dark
theme. **Kept local / private — not published** (gesh-core holds internal trading IP).

### View locally

```bash
./docs/serve.sh          # → http://127.0.0.1:8090/   (landing → both dashboards)
./docs/serve.sh 9001     # custom port
```

Or just open `docs/index.html` in a browser directly.
