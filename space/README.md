---
title: SZL Constellation
emoji: 🌌
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 6.26.0
python_version: '3.13'
app_file: app.py
pinned: true
short_description: Estate map of SZL sources, receipts and live Hub state
license: apache-2.0
tags:
  - szl
  - governed-ai
  - receipts
  - holographic
  - constellation
---

# SZL Constellation - the living archive

49 estates, unarchived as light.

[Canonical GitHub source](https://github.com/szl-holdings/szl-constellation) |
[Receipt ledger](https://huggingface.co/datasets/SZLHOLDINGS/szl-lake) |
[Product](https://a-11-oy.com) |
[Proof](https://a11oy.net)

## Shader Fabric v1.1 - deployed, hash-verified

Open the hologram: https://szlholdings-szl-constellation.hf.space/fabric

In the September 24 snapshot, served engine and demo bytes matched GitHub source
82399278d299db78e88070e6f88e5b8fbc6585d3 by SHA-256; this is not a claim
about the current main branch. `/healthz` reports the running app.py hash. The
headless Edge observation was WEBGL_CONTEXT_INITIALIZED, 49 estates, 0 dropped
(https://huggingface.co/datasets/SZLHOLDINGS/szl-lake/blob/main/receipts/2026-09-24/constellation-fabric-render-20260924T222547Z.json).
No-WebGL browsers get an explicit static honest fallback.

Runtime receipt: https://huggingface.co/datasets/SZLHOLDINGS/szl-lake/blob/main/receipts/2026-09-24/constellation-fabric-runtime-20260924T214759Z.json

| State | Visual treatment | Meaning |
|---|---|---|
| MEASURED | Bright | Measured evidence exists |
| PROMOTED | Bright cool | Promotion gate passed |
| UNKNOWN | Neutral | No claim |
| BLOCKED | Dim | Gate denial is visible |
| INVALID | No rendering | Fail-closed input or comparison |

## Developer start

~~~text
git clone https://github.com/szl-holdings/szl-constellation.git
cd szl-constellation
git checkout 82399278d299db78e88070e6f88e5b8fbc6585d3
python -m http.server 8000
# open http://localhost:8000/holo/demo.html
~~~

## Governance

Hub repository: SZLHOLDINGS/szl-constellation

`GET /api/build-info` reports the running Hub revision and a separate
`publisher_binding` with the protected GitHub source revision and publisher run
declared in `szl-source-binding.json`. `LOCAL_BYTES_VERIFIED` means the running
Space recomputed every managed file's size and SHA-256, the managed-tree digest,
and the packaged manifest hash. It does not independently attest the GitHub
commit at request time. A missing or inconsistent manifest makes `GET /readyz`
return 503; `GET /healthz` remains a basic process-health check.

- Source authority: https://github.com/szl-holdings/szl-constellation
- Current publisher-declared source: inspect `publisher_binding.source_revision`
  and its state at `GET /api/build-info`; confirm the protected publisher run
  and immutable Hub revision independently before treating it as deployed.
- Historical source snapshot: 82399278d299db78e88070e6f88e5b8fbc6585d3
  (September 24 render receipt above).
- Receipt authority: https://huggingface.co/datasets/SZLHOLDINGS/szl-lake
- Formal campaign: https://github.com/szl-holdings/lutar-lean/issues/287
- Incident: INC-05-ORIGIN-SHA-LAG-4 CLOSED_VERIFIED 2026-09-24 (a-11-oy.com/honest git_sha equals GitHub a11oy main).
- Evidence boundary: verification proves integrity and declared origin, not availability, readiness, or performance.

Doctrine v11 - nothing glows that did not earn it.
