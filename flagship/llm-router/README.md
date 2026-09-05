# llm-router — the Routing Command (staged)

Staged for `szl-holdings/szl-router` per the 2026-09-04 revival charter
(`docs/REVIVED-2026-09-04-llm-router.md`). The repo is archived (read-only);
after the owner unarchives it, this directory drops in as the flagship skeleton.

## What it is

The governed traffic plane. Every request's engine/model/vertical placement is
an advisory decision with a recomputable receipt. Deny-by-default: no configured
engine, no route.

## Endpoints

- `GET /api/router/engines` — the six engines, honest BLOCKED when unconfigured
- `GET /api/router/models` — the org's routable model line (from the Hub API, live)
- `POST /api/router/route` — admission: picks an engine by policy + declared cost,
  returns ADVISORY verdict + sha256 receipt. Never executes inference itself.
- `GET /healthz` — liveness with doctrine stamp
