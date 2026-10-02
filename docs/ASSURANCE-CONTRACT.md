# Constellation assurance integration

The Sentra facade's current contract is read-only receipt verification, not an
admission or approval service. The older GATE/YAWAR/plane-registry controls do not
describe the deployed facade and must not be restored as a compatibility fix.

## Runtime paths

| Surface | Contract |
| --- | --- |
| `GET /api/assurance/status` | Read the fixed Sentra `/api/live` URL and validate its canonical verifier manifest. Return `REPORTED` on the recognized contract; HTTP 503 / `UNAVAILABLE` on an unavailable or incompatible contract. |
| Assurance panel | Show the contract readback and a fixed link to the canonical receipt-verifier UI. No receipt data is submitted by this panel. |
| `GET /api/sentra/planes` | HTTP 410 with `RETIRED_CONTRACT` and the replacement status route. No upstream request. |
| Legacy Python gate/chain helpers | Return `UNAVAILABLE` / `RETIRED_CONTRACT` without network requests or local substitute verdicts. |

The status response always says `receipt_verified: false` and
`approval_granted: false`. A reachable facade, an HTTP 200 response, and a
manifest declaring `LIVE` do not verify a receipt. The canonical verifier can
return `INCONCLUSIVE` with `ok: true`; the operator must inspect the actual
signature, payload-digest, and hash-chain checks and the overall verdict there.
Verification does not authorize action execution.

The links are fixed, not supplied by upstream response fields:

- Facade: `https://szlholdings-sentra.hf.space/api/live`
- Verifier manifest: `https://szlholdings-a11oy.hf.space/api/a11oy/v1/verify/receipt`
- Human verification UI: `https://szlholdings-a11oy.hf.space/verify`

The response is decoded by the same bounded, strict-JSON helper used by the
other object APIs. Its envelope, source, schema, request route, evidence types,
and human-UI route must match the recognized contract. It does not follow
manifest-supplied destinations. The status receipt is an unsigned recomputable
hash of the reported contract, not a signature-verification result.

## Source and publication boundary

This migration follows the materializer and verifier inspected at A11oy source
`65c0a2cfd96d1171f6f5ba828d67a0228390b6d3` on October 1, 2026 (America/New_York):

- `scripts/hf_publish_vertical_flagships_v4_impl.py`
- `szl_public_verify.py`

It changes only Constellation. It does not modify A11oy or Sentra, revive retired
aliases, introduce a provider writer, grant approval, or broaden the public
facade's capabilities. The existing GitHub-main publisher remains the only
deployment path; passing local tests or publishing a PR is not evidence
that this change is already live.
