# W27 HF batch-1 audit #1: szl-constellation leader study (propose-only)

Date: 2026-11-24. OUROBOROS program, HF SZLHOLDINGS space audit batch 1, item 1.
Governing seat ruling nonce: CONSTK1-20261124T002340Z (Kimi GO_MERGES for this study doc; plan edits incorporated verbatim below).

Facts (measured 2026-11-23/24):
- the living archive: 49 estates rendered as WebGL2/WebGL1 hand-rolled GLSL hologram,
  8 verticals wired to real repos; source-fenced anonymous public runtime witness,
  read-only source-bound HF drift witness, Hub-card graph edges with source-bound
  interactive provenance, evidence-bound 3D lenses, bounded fan-out channels with
  honest drop accounting, estate-map additive schema (W26L D4).
- Doctrine v11, fail-closed, Apache-2.0, GitHub=source HF=mirror, receipts to szl-lake.

Leaders studied (2026-11-24):
1. WebGPU ecosystem 2026: GA in Chrome, Safari, and Firefox; WGSL mature; three.js and
   Babylon native WebGPU backends. Hand-rolled WebGL2/GLSL is now the legacy path.
   (appscale.blog WebGPU in Production 2026; ttlab WebGPU+WGSL ecosystem deep dive 2026;
   rivendellweb WebGPU 2026 update)
2. visgl deck.gl: WebGL2 and WebGPU layers for large datasets, GPU layers over JSON,
   usable as script tag, npm package, or pydeck; the high-performance large-scale
   browser visualization leader. (github.com/visgl/deck.gl ~14.6k stars)
3. Current HF Spaces deploy doctrine (gradio docker guides, spaces docs 2026).

Honest gaps:
- Rendering estate on the legacy WebGL path while the WebGPU successor is GA in major browsers.
- Org graph is growing; hand-rolled shaders carry maintenance cost.
- Graph layout is CPU; no GPU compute stage.

SCALE CLAIM - PRECISE DEFINITION REQUIRED (governing seat edit, verbatim):
"191 repositories versus 49 rendered estates is not automatically a 191-node
renderable graph. The study must define the repository-to-estate mapping and
separately report nodes, edges, visible elements, and interaction load."
No node/edge counts are claimed measured here; any implementation PR must measure first.

WEBGPU AVAILABILITY - QUALIFIED (governing seat edit, verbatim):
"Do not describe WebGPU as universally available without qualification. Record
browser, operating system, adapter, policy, remote-session, and headless-CI
limitations, with dated primary-source capability checks. Treat the supplied
secondary-source claims as unverified until checked against primary sources."

Absorb plan (ratified by governing seat, Kimi CONSTK1-20261124T002340Z, edits incorporated):
1. THIS PR: propose-only study doc (text-only). No runtime code, shader, dependency,
   CI, deployment, schema, or public Space behavior changes.
2. Later PR: WebGPU-first renderer with WebGL2 fail-closed fallback; WebGL1 last
   resort only. Fail-closed doctrine preserved at every failure point.
3. Later PR: honest benchmark receipts comparing hand-rolled GLSL vs deck.gl/pydeck
   WebGPU layers at measured full-org graph scale BEFORE any rewrite decision. No
   premature rewrite.
4. Later PR: WebGPU compute graph-layout stage with CPU fallback, gated on the
   measured node/edge counts from the mapping study.
Each implementation PR: separate CI, separate governing review, owner approval per
propose-only doctrine.

Non-goals: no renderer rewrite in this PR, no CI changes, no secrets.
