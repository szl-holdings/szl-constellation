# Cherry-Pick Brief — 2026-09-04

Method: fashion thinking. Gucci studied Tommy, kept the silhouette, made the rest
original. We do the same: pattern-level adoption, clean-room reimplementation under
Doctrine v11, receipts on everything. Silhouettes, never counterfeits. Every source
below was audited from public repo metadata on 2026-09-04.

## 1. SkyPilot — `skypilot-org/skypilot` (10.5k★, Apache-2.0)

The emailed link (liuxu623/skypilot) is a dead fork; the canonical project is
skypilot-org. The AI Compute Platform: multicloud GPU orchestration, spot recovery,
job queues, LLM serving/training, Slurm/TPU, cost optimization.

**Take:**
- The catalog pattern (`skypilot-catalog`) — a registry of reusable, tested task specs
- Spot/preemption-aware scheduling + cheapest-watt placement
- Task-YAML job descriptions as the unit of work

**Make it ours:**
- `szl-runbook-catalog` — DSSE-signed, receipted task specs (SkyPilot specs are unsigned)
- Extend `szl-energy-attest` cheapest-watt placement into the `szl-gpu-bridge` scheduler:
  preemption-aware, doctrine-gated, every scheduling decision emits a receipt
- Evolution line: they schedule compute; we schedule *governed, receipted* compute

## 2. ai-runtime-lab — `Ali-hey-0/ai-runtime-lab` (126★, Python)

Deterministic systems around non-deterministic LLMs: FSM, durable execution, retries,
DAGs, model routing, memory, multi-agent orchestration, prompt-injection security,
observability — 14 runnable proof-of-concept phases.

**Take:** the 14-phase curriculum structure and the FSM+durable-execution spine.

**Make it ours:** `governed-runtime-lab` under a11oy/platform — same phases, but every
state transition is Λ-gated and hash-chained; failure states are fail-closed by
construction, not convention. Their PoCs demonstrate; ours *attest*.

## 3. The Zeline plane — `Mftrferdinand/Zeline*` (68★ core)

A clean four-plane agent architecture: Eval (local-first agent eval), Trace (run
timeline viewer: tool calls, tokens, cost), Bench (latency/throughput/cost/memory),
Gateway (transport/session/auth adapters: Telegram, WhatsApp, webhooks).

**Take:** the plane separation. Our bench fleet already covers Bench.

**Make it ours:**
- Trace → a receipt-chain timeline viewer in `evidence-studio` (observation becomes
  tamper-evident evidence)
- Gateway → adapter layer in `hatun-mcp` (16 tools) for david-leads outreach surfaces
- Eval → fold agent-eval lanes into `governed-agent-bench` with fairness gates

## 4. xcontcom emergent systems (163★/154★/113★/112★, JS)

billiard-fractals, evolving-cellular-automata, neuroparticles (NN-driven particles,
genetic algorithms), fractogenesis. The best emergent-behavior browser work in the
audit set.

**Take:** neuroevolution particle fields + CA growth as first-class visuals.

**Make it ours:** the constellation's kernel rain becomes an evolving field — particles
seek the Second Brain under a governed fitness function; anatomy gains CA-grown organ
membranes. Their particles evolve for aesthetics; ours evolve against receipt-weighted
fitness and render the estate's actual health.

## 5. scientific-agent-skills — `Tyche-MKR/scientific-agent-skills` (98★)

165 validated, ready-to-use agent skills over 100+ scientific databases, on the open
Agent Skills standard (Cursor/Claude Code/Codex compatible).

**Take:** the validated skill-pack format and the skills-standard packaging.

**Make it ours:** SZL skill packs for hatun-mcp's 16 tools and the counsel/ayllu
council — doctrine-aware skills with per-skill receipts. Successor surface to the
archived szl-cookbook.

## 6. Also audited

- meta-success/AI-agents (89★, TS) + n8n-automation (68★) — workflow-automation
  patterns; feed the david-leads pipeline design
- Ali-hey-0/audio-ai-field-guide (109★) — ASR/TTS pipeline notes; park for a future
  counsel voice surface
- hackercondor (51★ lists), KaenBlaze, 0xAnamul, wderance/evvenoly — curated lists,
  portfolios, web3; nothing to take

## Standing rule

Pattern-level adoption only. Where any code is derived from an Apache-2.0 source, the
NOTICE and attribution ride along. Where a source is ambiguously licensed, we read the
idea and write our own. The estate's doctrine is the moat — receipts, fail-closed,
nothing fabricated.
