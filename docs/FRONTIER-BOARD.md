# Frontier Board — 2026-09-04

Every take from the wave-1 and wave-2 cherry-pick audits, mapped to its home in
the estate and its status. Nothing here is aspirational fog: SHIPPED means code
landed tonight; SEEDED means the contract/spec exists and a lane can execute;
TRACKED means scoped in a brief with a named home.

## Shipped tonight

| Take | Source | Home | Evidence |
|---|---|---|---|
| Receipted task-spec catalog | SkyPilot catalog pattern | szl-holdings/szl-runbook-catalog | repo + validator, 6/6 seeds admit (7d8693c4) |
| Tokenizer throughput lane | marcelroed/gigatoken | spec bench/tokenizer-throughput | catalog seed |
| Kernel console axes (FLOPs/memory/roofline) | MatthewBonanni/attn-viz | spec kernel-fixture/attention-trio | catalog seed |
| Receipted GH↔HF mirror workflow | Yikun/hub-mirror-action | szl-runbook-catalog/.github/workflows/mirror.yml | needs HF_WRITE_TOKEN secret |
| Estate wiring record | tonight's org audit | spec vertical-asset/estate-wiring-2026-09-04 | catalog seed |
| Nemo regeneration envelope | SkyPilot scheduling metadata | spec gpu-jobspec/nemo-v3-rerun | catalog seed; signing stays owner-side |
| Vertical consoles + JSON backend | estate audit | HF Space SZLHOLDINGS/szl-constellation | 9afbfa19 |
| Holographic constellation v3 | estate audit | Space holo/index.html | 92a23e4b |

## Seeded for the next lane (contracts written)

| Take | Source | Home |
|---|---|---|
| Territories + receipt-roads in the hologram | anvaka map-of-github / VivaGraphJS | constellation holo v4 |
| Trust-path queries ("how does killinchu trust puriq-live") | anvaka ngraph.path | constellation /api/constellation/paths |
| Hilbert-curve receipt-chain visualizer | cortesi/spacecurve | evidence-studio |
| dev-loop watcher idioms | cortesi/devd + modd | platform tooling |
| Config-driven experiment plane | snap-stanford/GraphGym | szl-engine-bench config layer |
| GNN over the receipt graph (drift detection) | PyG + GraphRNN + P-GNN | new lane: szl-graph (phase 1: export estate graph from manifest) |
| RL over graph edits for governed action search | bowenliu16/rl_graph_generation | szl-graph phase 3, research-flagged |
| Learned SAT-formula generation | JiaxuanYou/G2SAT | lutar-lean research lane |
| Architecture-as-graph kernel analysis | facebookresearch/graph2nn | kernel-fixture/attention-trio v2 |
| 14-phase governed runtime curriculum | Ali-hey-0/ai-runtime-lab | governed-runtime-lab under platform (FSM + durable execution, Λ-gated) |
| Trace timeline viewer | Zeline-Trace | evidence-studio |
| Gateway adapters (Telegram/WhatsApp) | Zeline-Gateway | hatun-mcp + david-leads |
| Agent eval lanes | Zeline-Eval | governed-agent-bench |
| Skill packs (Agent Skills standard) | Tyche-MKR/scientific-agent-skills | hatun-mcp skills/ + counsel council |
| Persistent council memory + reflection | echocolony/Colony | ayllu + szl-frontier + ouroboros (no token economy - receipts only) |
| Audio pipeline notes | Ali-hey-0/audio-ai-field-guide | counsel voice surface (parked) |

## Alignment (no code taken)

vLLM orbit (MatthewBonanni, DarkLight1337, Yikun/vllm-ascend, Volcano): keep
szl-engine-bench vendor-neutral and publishable; Volcano-style batch semantics
inform szl-gpu-bridge queues.

## Standing rule

Silhouettes, never counterfeits. Apache-2.0/MIT derivations carry NOTICE.
Ambiguous licenses are read for ideas and rewritten clean. Doctrine v11.
