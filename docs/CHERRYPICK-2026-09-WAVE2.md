# Cherry-Pick Brief — Wave 2 (Favorites + Following deep audit) — 2026-09-04

Same method: silhouettes, never counterfeits. Pattern-level adoption, clean-room
reimplementation, receipts on everything. All metadata audited live on 2026-09-04.

## A. The graph frontier (your six favorites)

| Repo | ★ | What it is | What we take |
|---|---|---|---|
| pyg-team/pytorch_geometric | 24,061 | The GNN library for PyTorch | Message-passing idiom as an estate primitive: the constellation IS a graph - estates as nodes, receipts as edges. A `szl-graph` lane: GNN over the receipt graph (anomaly = broken chain neighborhood) |
| snap-stanford/GraphGym | 1,903 | Config-driven GNN design/eval platform | The Gym pattern for our bench fleet: declarative experiment configs + standardized eval -> extend szl-engine-bench/retrieval-bench with a config plane |
| JiaxuanYou/graph-generation (GraphRNN) | 733 | Autoregressive deep graph generation | Generative estate modeling: learn the graph of a healthy deployment; flag drift when the live estate graph diverges |
| JiaxuanYou/P-GNN | 402 | Position-aware GNNs | Positional encoding for estate nodes - an estate's embedding includes WHERE it sits in the constellation, not just what it is |
| JiaxuanYou/G2SAT | 50 | Learning to generate SAT formulas | Bridge to lutar-lean: learned generation of verification-shaped problems for the Lean estate (research lane, clearly marked) |
| bowenliu16/rl_graph_generation (GCPN) | 359 | RL graph/molecule generation | RL over graph edits -> governed action search: actions as graph mutations, every candidate receipted before admission |
| facebookresearch/graph2nn | 156 (archived) | Graph structure OF neural networks | Architecture-as-relational-graph analysis for the kernel line: characterize szl-receipt-attn / szl-block-kv / szl-maskmod by their compute graphs |

**Estate evolution:** the constellation stops being a picture of the estate and becomes
an instrument over it. Phase 1: export the real estate graph (repos, Spaces, models,
datasets, receipt links) from the audit data. Phase 2: GNN lanes in the bench fleet.
Phase 3: drift detection = live graph vs receipted graph.

## B. The map/render frontier — anvaka

city-roads (9.6k), VivaGraphJS (3.9k, WebGL graph drawing), ngraph.path (3.1k,
pathfinding), map-of-github (2.9k - repos as a navigable map of countries).

**Take:**
- map-of-github's core metaphor, upgraded: our constellation already renders estates as
  orbs; his maps render *regions with borders*. v4: tier-shells become territories with
  labeled provinces (Core, Bench, Frontier...), roads = receipt flows
- VivaGraphJS's force-layout-at-scale idioms for the 2D fallback mode
- ngraph.path: shortest-path between any two estates through receipt links -
  "how does killinchu trust puriq-live?" answered as an actual path, rendered

**Make it ours:** his maps are static art over GitHub; ours are live instruments over
receipted truth. Every border, road, and path is computed from the manifest + pings.

## C. The systems frontier

- **marcelroed/gigatoken (4,075★, Rust)** — LM tokenization at GB/s. Take: tokenizer
  throughput as a first-class lane in szl-engine-bench (TTFT means nothing if
  tokenization is the bottleneck); Rust-grade perf discipline for hot paths.
- **MatthewBonanni/attn-viz (7★)** — interactive visualizer for attention variants
  (MHA/GQA/MQA/MLA) with FLOPs/memory costs and per-GPU rooflines. Take: this is the
  missing display panel for OUR kernel trio (szl-receipt-attn, szl-maskmod,
  szl-block-kv) - a kernel-console tab with shape/cost/roofline math, honest fixture
  labels, wired into quant-bench.
- **Yikun/hub-mirror-action (710★)** — mirrors repos between GitHub/Gitee/GitLab.
  Take: the CI pattern, pointed at GitHub<->HF. The constellation mirror I hand-pushed
  tonight becomes an automated, receipted sync workflow (szl-constellation + Space
  stay in lockstep; every sync emits a receipt).
- **cortesi** — devd (3.5k, local dev server), modd (3k, fs-watch process runner),
  spacecurve (530, Hilbert curves). Take: devd/modd DX idioms for the estate dev loop;
  Hilbert-curve layout as the receipt-chain visualizer in evidence-studio - a chain
  rendered as a space-filling curve makes gaps and forks visible at a glance.

## D. The agent-society frontier

- **echocolony/Colony (2★, new, TS)** — persistent multi-agent civilization: living
  memory, subconscious reflection, organizations, economy. Take the *architecture
  idea* only: persistent agent society with reflection cycles -> the ayllu council
  gains persistent memory via szl-frontier (Memory Covenant) and reflection via
  ouroboros loop-tax cycles. Skip the stablecoin economy entirely - our economy is
  receipts, and approval never lifts a hard deny.

## E. The vLLM orbit (alignment map, no direct takes)

MatthewBonanni (vLLM maintainer), DarkLight1337 (vLLM core contributor), Yikun
(vllm-ascend, Apache Spark PMC, Volcano reviewer). Value here is alignment, not code:
vLLM is already an engine target in szl-engine-bench; Volcano-style batch scheduling
informs the szl-gpu-bridge queue; keep the bench harness vendor-neutral and honest so
results are publishable in those circles.

## F. Audited, nothing to take

liuxu623 (Hackintosh EFIs - the skypilot fork was the only signal, canonical repo
covered in wave 1), SDavidJake907 (no public repos), AhmedDabish, foxier25,
Carlota-1, cambot86, phireskey, zautumnz, FeixLiu, standardgalactic, KBB99, flyxion,
madanimkhitar22-beep, mwakidenis, yumiaura, JohnMwendwa, Harry-Chen (Debian
packaging craft, respected, no pattern we lack).

## Standing rule (unchanged)

Pattern-level adoption. Apache-2.0/MIT sources get NOTICE attribution where derived;
ambiguous licenses are read for ideas and rewritten clean. The doctrine is the moat.
