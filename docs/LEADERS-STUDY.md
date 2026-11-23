# Domain Leader Study — szl-constellation (living archive WebGL hologram)

OUROBOROS phase-3, cohort-02 tranche-2, Kimi ruling W26-C2T2-KIMI-20261123-ASK (GO, 7 bindings). PROPOSE-ONLY, DRAFT. Documentation only, no implementation in this PR.

## Current state (repo inspection 2026-11-23)
Python repo; description: SZL Constellation, the living archive: 49 estates unarchived as a WebGL hologram, 8 verticals wired to their repos; fastapi + huggingface Spaces companion measured live in the spaces census. Topics: fastapi, governed-ai, hologram, huggingface, python, spaces.

## Domain leaders studied
| Leader | What they have | Key sources |
| --- | --- | --- |
| FastAPI (official websockets docs) | The canonical bidirectional channel for live-updating dashboards, with typed send/receive contracts — the reference pattern for pushing estate state to the browser without polling | fastapi.tiangolo.com/advanced/websockets/ (accessed 2026-11-23) |
| three.js InstancedMesh | The reference WebGL technique for rendering thousands of similar objects (estate nodes) in one draw call — the standard answer for live holograms that must stay smooth at scale | three.js official documentation (InstancedMesh) (accessed 2026-11-23) |

## What the leaders do better
- FastAPI keeps the channel contract typed and documented, so a live push can be reasoned about and receipted, not reverse-engineered from the client.
- InstancedMesh is the leader's scale pattern: 49-estate + vertical-wire visualizations stay in-budget only with per-instance attributes, not per-node scenes.

## Gaps
- Description-measured wiring exists, but no documented channel contract (message types, reconnect/ordering policy) for the live surface was found in card scope.
- No documented draw-call budget or per-instance attribute policy for the hologram's node count.

## Ranked #1 absorb proposal (NOT implemented in this PR)
Document a typed websocket message contract for estate-state pushes (schema + ordering/reconnect policy) and an InstancedMesh-class draw budget receipt for the hologram at full estate size (49 estates + 8 verticals). Expected benefit: live archive becomes contract-driven externally verifiable; render smoothness becomes measured, not assumed. Cost/risk: low; docs-contract + budget definition only, additive. Validation: contract page rendered from schema; budget receipt reproducible on a headless run. Rollback: removal only.

## Sources
- FastAPI websockets: https://fastapi.tiangolo.com/advanced/websockets/ (accessed 2026-11-23)
- three.js InstancedMesh docs: https://threejs.org/docs/#api/en/objects/InstancedMesh (accessed 2026-11-23)
