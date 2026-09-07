# Archive Revival Constellation v2

A read-only, source-bound map of the archived SZL Holdings estate.

The surface explains why four repositories remain active source owners, where 24 superseded repositories consolidate, and why six historical repositories remain immutable. It does not mutate GitHub, publish to Hugging Face, probe a runtime, or claim that the contract's expected state equals live provider state.

## Canonical classification

The local registry is bound to:

```text
repository: szl-holdings/.github
path:       governance/archive-portfolio-v2.json
merge SHA:  79a8f2add42913b0831260574145437efe56af4a
```

Exact source-owner allowlist:

```text
szl-atelier
szl-mesh
szl-router
uds-bundles
```

Every other row is either `CONSOLIDATE` or `HISTORICAL`. The loader rejects duplicate names, count drift, source-owner drift, malformed Hub showcase identities, historical successors, and any local row that claims provider evidence.

## Run

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r frontier/archive_revival_v2/requirements.txt
SOURCE_REVISION="$(git rev-parse HEAD)" \
  python -m uvicorn app:app --app-dir frontier/archive_revival_v2 --host 127.0.0.1 --port 7860
```

Open `http://127.0.0.1:7860`.

## API

| Route | Purpose |
|---|---|
| `GET /healthz` | Process liveness only |
| `GET /readyz` | Controlled-file and registry validation |
| `GET /api/source` | Source revision, controlled hashes, and explicit no-write authority |
| `GET /api/archive-revival` | Filterable, deterministic 34-repository lineage registry |
| `GET /api/archive-revival/{name}` | One exact local contract row with unavailable provider/runtime state |

## Truth boundary

```text
CLASSIFIED
!= UNARCHIVED
!= SOURCE_PR
!= MERGED
!= HUB_PUBLISHED
!= RUNTIME_READY
!= EXACT_READBACK_VERIFIED
```

The interface displays the relationship between archived source and canonical successor. It does not copy source histories or make Constellation the owner of those implementations.

## Test

```bash
python -m pytest -q frontier/archive_revival_v2/tests
```

## Container

```bash
docker build -f frontier/archive_revival_v2/Dockerfile -t archive-revival-v2 .
docker run --rm -p 7860:7860 -e SOURCE_REVISION="$(git rev-parse HEAD)" archive-revival-v2
```

The container runs as UID/GID `10003:10003`.
