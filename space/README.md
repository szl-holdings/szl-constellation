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

Served engine and demo bytes match GitHub main 82399278d299db78e88070e6f88e5b8fbc6585d3 by SHA-256, and /healthz reports the deployed app.py hash. Real-browser WebGL rendering is not asserted by the receipt; no-WebGL browsers get an explicit static honest fallback.

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

- Source authority: https://github.com/szl-holdings/szl-constellation
- Merged source: 82399278d299db78e88070e6f88e5b8fbc6585d3
- Receipt authority: https://huggingface.co/datasets/SZLHOLDINGS/szl-lake
- Formal campaign: https://github.com/szl-holdings/lutar-lean/issues/287
- Incident: INC-05-ORIGIN-SHA-LAG-4 remains OPEN.
- Evidence boundary: verification proves integrity and declared origin, not availability, readiness, or performance.

Doctrine v11 - nothing glows that did not earn it.