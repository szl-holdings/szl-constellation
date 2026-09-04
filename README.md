# SZL Constellation — the living archive

**49 estates, unarchived as light. 8 verticals, wired end-to-end.**

Source mirror of the Hugging Face Space [`SZLHOLDINGS/szl-constellation`](https://huggingface.co/spaces/SZLHOLDINGS/szl-constellation).

## What it is

- **`holo/index.html`** — the hologram: a three.js WebGL star map. 49 estate orbs on nine tier shells orbit the trinity — **Second Brain** (teal core), **Anatomy** (violet core), and the **Ouroboros** ring that never stops. Every estate is wired to its hub by a neural thread carrying endless synapse pulses. Kernel rain falls inward into the second brain, forever. Live satellites ring the outside. Orbs brighten to REACHABLE only when they answer a live ping from the viewer's browser.
- **`app.py`** — the Gradio app + FastAPI backend. Eight per-vertical consoles (Killinchu, PURIQ, Terra, Aegis, Lyte, Counsel, Finance, David Leads), each wired to its audited repos, kernels, models, and datasets, each with a real computing widget (OSINT mesh query, Λ gate, receipt verifier, ouroboros ledger, BM25, quant curve, live probes).
- **`estates.json`** — the 49-estate manifest (consolidation receipt run 33824259800) + the 16-satellite live lattice + the 12-kernel line.
- **`verticals.json`** — the wiring map: every vertical bound to its real GitHub repos, HF Spaces, kernels, models, datasets, and live endpoints (audited 2026-09-04: 113 org repos, 44 models, 40 datasets, 17 Spaces).

## JSON backend

| Route | Truth |
|---|---|
| `/api/constellation/manifest` | DECLARED manifest, hash-receipted |
| `/api/verticals` | The wiring map |
| `/api/verticals/{id}/status` | Live probes — MEASURED or UNAVAILABLE |
| `/api/kernels` | Kernel line measured from the Hub API at request time |

Every response carries an UNSIGNED_HONEST receipt: a SHA-256 that commits to the
payload, verifiable by recomputing.

## Doctrine v11

Nothing glows that didn't earn it. REACHABLE is computed, DECLARED is receipted,
UNMEASURED is reported — never fabricated. Λ = Conjecture 1 (advisory).

Apache-2.0 · SZL Holdings
