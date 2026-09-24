<div align="center">

# S Z L   C O N S T E L L A T I O N

**The living archive — 49 estates rendered as light.**

`GLSL` · `WebGL2 + WebGL1` · `fail-closed` · `Apache-2.0` · Doctrine v11

[HF Space (runtime)](https://huggingface.co/spaces/SZLHOLDINGS/szl-constellation) · [Build receipt (receipted → szl-lake)](https://huggingface.co/datasets/SZLHOLDINGS/szl-lake/blob/main/receipts/2026-09-23/holo-shader-fabric-v1.json) · [Org](https://github.com/szl-holdings)

</div>

---

## What this is

A holographic, computable map of the whole SZL Holdings estate. Every orb on the field is a real repository, kernel, model, or dataset — and crucially, the renderer is governed by the same doctrine as the rest of the stack: **nothing glows that didn't earn it.**

This repo now carries the **SZL Shader Fabric** (`holo/`), a clean-room GLSL estate hologram engine: estates are admitted through a fail-closed validation gate, and each one renders at a brightness keyed to its declared honesty state. No runtime deployment of the Fabric is claimed by this README — the engine is source-live; the Gradio Space runs the archive panels (Sept 8 image).

## Run the hologram in 20 seconds (dev path)

```bash
git clone https://github.com/szl-holdings/szl-constellation.git
cd szl-constellation
python -m http.server 8000
# open http://localhost:8000/holo/demo.html
```

No build step, no dependencies, no API keys. The engine reads `estates.json` at the repo root and projects the estate registry into the field. If WebGL is missing, you get an honest static fallback notice — never a fake interface.

## How to read the field

| State | Gain | Meaning |
|---|---|---|
| **MEASURED** | full glow | The estate carries measured evidence — receipts, benches, signed runs |
| **PROMOTED** | bright, cool tint | Passed a promotion gate |
| **UNKNOWN** | neutral | No claim — reported, never fabricated |
| **BLOCKED** | dim | A gate denied; the field shows the denial |
| **INVALID** | nothing | Cross-revision or malformed comparison — it renders *nothing*, and the HUD counts the drop |

Malformed estate entries are dropped at admission and the HUD displays the drop count — fail-closed is visible, not implied.

## Repo map

```
.
├── estates.json            # canonical estate registry (the data the field renders)
├── verticals.json          # vertical → repo/kernel/model/dataset wiring
├── holo/
│   ├── szl-shader-fabric.js  # the GLSL engine (clean-room, Apache-2.0)
│   ├── demo.html             # self-contained showcase page with HUD
│   └── command.html          # earlier command surface
├── frontier/archive_revival_v2/  # archive-revival lineage showcase
├── space/                  # Gradio Space runtime (hosted on HF)
└── docs/
```

## For investors (the 60-second read)

This is the estate-as-product proof: one shader field whose every glow point is backed by a checkable artifact. Clicking any estate lands on a repo that itself ships hash-chained receipts. Scale check: [SZLHOLDINGS on Hugging Face](https://huggingface.co/SZLHOLDINGS) — 49 models, 41 datasets, and 27 Spaces (public inventory snapshot observed 2026-09-23) — including a [61K-download OSINT corpus](https://huggingface.co/datasets/SZLHOLDINGS/killinchu-osint-corpus) and hardware-trainable small models like [SZL-Khipu-1.5B](https://huggingface.co/SZLHOLDINGS/SZL-Khipu-1.5B). Verification proves integrity and origin, never accuracy — that boundary is stated on every card, and it is the company's moat.


## Authority and wiring

| Layer | Canonical location | Boundary |
|---|---|---|
| Canonical source | [https://github.com/szl-holdings/szl-constellation](https://github.com/szl-holdings/szl-constellation) | Inspectable source and Git history |
| Hosted runtime | [https://huggingface.co/spaces/SZLHOLDINGS/szl-constellation](https://huggingface.co/spaces/SZLHOLDINGS/szl-constellation) | Separate deployment; not automatically GitHub main |
| Receipt ledger | [https://huggingface.co/datasets/SZLHOLDINGS/szl-lake](https://huggingface.co/datasets/SZLHOLDINGS/szl-lake) | Append-only evidence receipts |
| Estate pin | [https://github.com/szl-holdings/szl-pin](https://github.com/szl-holdings/szl-pin) | Deterministic source-head commitment |
| Product | [https://a-11-oy.com](https://a-11-oy.com) | Operator/product surface |
| Proof | [https://a11oy.net](https://a11oy.net) | Public proof and known bounds |
| Formal campaign | [https://github.com/szl-holdings/lutar-lean/issues/287](https://github.com/szl-holdings/lutar-lean/issues/287) | Open Lambda / Lean campaign |

**Alignment boundary:** Shader Fabric v1.1 is source-live at GitHub commit
[\b232045\](https://github.com/szl-holdings/szl-constellation/commit/bb232045a3d345d7e65598e7cd8c8400a131b91d).
Its source landing receipt is in
[szl-lake](https://huggingface.co/datasets/SZLHOLDINGS/szl-lake/blob/main/receipts/2026-09-23/holo-shader-fabric-v1.json).

> **No runtime claim:** source state and hosted Space state remain separate until a
> deployment receipt binds source SHA, Space revision, route check, and runtime evidence.

## Verify, don't trust

- Every landing ships a receipt to [SZLHOLDINGS/szl-lake](https://huggingface.co/datasets/SZLHOLDINGS/szl-lake) (UNSIGNED_HONEST unless signed).
- The estate pinning layer: [`szl-pin`](https://github.com/szl-holdings/szl-pin) — one SHA-256 commits to every repo head. Drift is never silent.
- Mutations to this README are source-level claims; runtime truth is only what you can recompute.

---

<sub>SZL Holdings · governed, receipted, verifiable · Λ = Conjecture 1 (advisory, never a theorem) · trust ceiling 0.97</sub>