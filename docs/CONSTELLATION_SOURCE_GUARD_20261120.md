# Constellation source-bound guard — source-only, not a deployment

**Owner:** `szl-holdings/szl-constellation`. **Canonical source:** protected GitHub `main`. **Targets:** fixed in `tools/constellation_targets.py`.

## Observed incident (November 20, 2026 UTC)

A truly anonymous Hugging Face `GET /api/spaces/SZLHOLDINGS/szl-constellation-staging` returned HTTP 200, `private=false`, stage `RUNNING`, repo revision `cce209a9ee6cd2d6806ddc9833e74934431500c0`. But canonical source declares this **staging** Space `private` with `wake_if_sleeping=false`. This is a visibility contradiction, **not** a reason to make it public or copy staging into production. The owner must determine whether that exposure was intentional, then approve any correction separately. No visibility change was made by this patch.

The public production Space returned HTTP 200, `private=false`, hub revision `eee04e0d8c07bc8712712e4c7b7ad211ef78f0ad`, provider stage `RUNNING`. Its current `szl-source-binding.json` says GitHub `main@fbb68c311f5ab1a38c5d3e71433562337c562f16`. **Stage and matching source identity do not establish authenticated rendering, health, independent evaluation, signed receipts or production admission.**

## Workflows, deliberate separation

The proposed workflow is retained as **non-executable source** at `docs/constellation-source-guard.workflow.proposed.yml`: the connected GitHub OAuth credential was denied permission to create `.github/workflows/constellation-source-guard.yml` without a `workflow` scope. **No new CI job or manual dispatch is installed by this PR.** If separately installed by an authorized owner after review, it runs offline negative controls on scoped PRs and runs live Hub drift observation only on manual dispatch, without a schedule, provider writes, DNS, Worker, queue, secret-store, hardware or model operations.

If private staging is inaccessible or `CONSTELLATION_HF_READ_TOKEN` is missing, the outcome is `UNKNOWN`—**never** PASS and never falsely reported as a missing Space. A publicly visible staging Space is a verifiable `DRIFT` without any credential. The read token must be scoped to **read-only** on the staging Space, supplied by the GitHub Actions secret only; never give it to agents or log it. Redirects with credentials to another origin are denied.

The production publisher's existing path triggers are left unchanged. This PR adds only new `tools/constellation_source_guard.py`, `tests/test_constellation_source_guard.py`, this document and the **inert workflow proposal** under `docs/`—all outside the existing publisher's listed deployment paths. The new tests are locally verified but do not yet constitute a GitHub required check. Installation of the workflow and enforcement of any check require separate authorization and exact-head review. Do **not** dispatch the production publisher or treat merging this source proposal as deployment approval. No branch-protection changes.

## Verifiable contracts

The guard verifies exact owner, target, declared visibility and SHA-40 of the GitHub source; source-binding schema/state, source repository and revision, managed-file metadata (bounded path/size/hash) and managed-tree digest; and remote managed-file bytes at the immutable Hub revision. It independently reconstructs the complete source file inventory from exact Git **blob bytes**, avoiding Windows checkout line-ending translation, and requires the Hub's independent immutable tree listing to contain exactly that file set plus `szl-source-binding.json`. An omitted publisher file, extra Hub-side file, or altered byte is `DRIFT`; an incomplete listing or missing Git checkout becomes `UNKNOWN`. A matching record remains only `PASS_OBSERVED_UNSIGNED`. This does **not** cryptographically prove the Hub commit's signer, its provenance, or application execution.

`PASS_OFFLINE` means local policy syntax only. `PASS_OBSERVED_UNSIGNED` means anonymous or scoped source-byte observation, not signed readiness. `DRIFT` means a sourced conflict; `UNKNOWN` means unavailable evidence. Automated production authorization is always false. Conservative limits: 128 files, 6 MiB each, 32 MiB total, short GET timeouts.

## Model review, independent testing, and limitations

Kimi through scoped Ollama identified that comparing a Hub file only with the Hub-provided binding could miss files omitted by that binding; this was corrected by independent exact Git blob and Hub tree inventories, with adversarial tests for omitted and additional files. Separately elicited local Ministral proposed a staging/token interpretation inconsistent with the fixed source declaration; existing tests cover the forged-private response, unknown-without-token outcome and public staging mismatch. Model review is neither human approval nor a signer. On BETTERWITHAGE, **29 deterministic tests passed**, structural source verification passed, and live unauthenticated production readback matched 48 managed files. Staging returned `DRIFT` due its public visibility. The Hub publication binding remains **unsigned** and production admission is **HOLD**.

## Manual reproduction

```sh
python -B -m unittest discover -s tests -p 'test_constellation_source_guard.py' -v
python -B tools/constellation_source_guard.py --mode offline
# Read-only, current protected main SHA supplied by operator:
python -B tools/constellation_source_guard.py --mode live \
  --target production --source-sha <exact-main-40-hex>
```

Private staging should remain `UNKNOWN` if authenticated read access has not been deliberately configured, unless its public exposure is independently detected. Do not use `UNKNOWN` as a green production gate. The owner should separately reconcile the observed staging visibility and document a readback before any production or secret-management change.
