# Consolidation of Record — Sentra absorbs Aegis — 2026-09-04

**Directive:** owner. *"Aegis fully consolidated into Sentra; Sentra is the sole
flagship for assurance."*

## State change

| Surface | Before | After |
|---|---|---|
| SZLHOLDINGS/aegis-assurance (Space) | assurance surface | DECOMMISSIONED — 404s by design; mission absorbed |
| SZLHOLDINGS/sentra (Space) | cybersecurity-intelligence flagship (Domain Experience v4) | SOLE ASSURANCE COMMAND — GATE + YAWAR + EVIDENCE planes |
| szl-holdings/immune (repo) | defense-matrix engine | engine library under the sentra flagship (unchanged, links preserved) |
| szl-holdings/szl-defensive-control-plane (repo, private) | canonical product source | unchanged — remains sentra's canonical source |
| killinchu#386 gated-deletion contract | listed sentra + aegis-assurance as killinchu candidates | AMENDED by owner directive — sentra is flagship, not a deletion candidate; aegis is absorbed by sentra, not killinchu |

## The v5 flagship overlay (deploy artifact)

`spaces/sentra/app.py` in this repo carries the v5 build: the existing v4
contract preserved byte-for-byte in behavior (`/healthz`, `/api/live`,
`/api/source`, `/api/build-info`, `/.well-known/szl-source.json`), plus the
absorbed planes:

- `POST /api/sentra/gate` — admission evaluation over axis scores. Deny-by-default
  always; the Λ verdict is ADVISORY-PASS / ADVISORY-HOLD and never admits.
- `POST /api/sentra/yawar/verify` — receipt-chain verification, recomputed link
  by link (the immune plane's YAWAR semantics).
- `GET /api/sentra/planes` — the plane registry + this consolidation record.
- Embedded v5 front end with working GATE and YAWAR consoles, the consolidation
  banner, and the v4 attack-path visual language preserved.

## Deploy path (honest)

The sentra Space rejects direct writes and PR writes from connector sessions —
deploys are governed through the a11oy controller from the canonical repo. The
v5 overlay lands via PR to `szl-holdings/szl-defensive-control-plane` and ships
through that pipeline. Until it merges, `/api/sentra/planes` is the contract the
Space will answer; the constellation manifests already reflect the truth.

## Verification

After the deploy PR merges and the Space rebuilds:

```bash
curl -s https://szlholdings-sentra.hf.space/api/sentra/planes | python3 -m json.tool
curl -s -X POST https://szlholdings-sentra.hf.space/api/sentra/gate \
  -H 'Content-Type: application/json' \
  -d '{"scores":[0.9,0.95,0.99,0.92],"weights":[1,1,2,1]}'
# expect: state MEASURED, verdict DENY-BY-DEFAULT, advisory ADVISORY-*, receipt present
```

Doctrine v11 — decommissioned nodes are reported, never erased.
