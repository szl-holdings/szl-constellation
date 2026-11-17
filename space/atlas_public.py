"""Public-only, provenance-bound Hugging Face estate topology for a WebGL atlas.

Only anonymous Hugging Face Hub metadata is consulted. No private inventory,
weights, dataset rows, execution, writeback, training or authentication.
September vertical bindings are *declared source topology* and are matched
against the currently listed public assets; missing bindings remain absent.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

ORG = "SZLHOLDINGS"
SCHEMA = "szl.public-hub-holographic-atlas/v1"
MAX_SPACES, MAX_MODELS, MAX_DATASETS = 200, 400, 300
CACHE_SECONDS = 300
ROOT = Path(__file__).resolve().parent
_ALLOWED_NAME = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_TIERS = ("space", "model", "dataset")
_limits = {"space": MAX_SPACES, "model": MAX_MODELS, "dataset": MAX_DATASETS}
_cache_lock = threading.Lock()
_cache: tuple[float, dict[str, Any]] | None = None


class AtlasError(ValueError):
    pass


def _utc(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _asset_url(kind: str, name: str) -> str:
    base = {"space": "spaces", "model": "", "dataset": "datasets"}[kind]
    prefix = ("https://huggingface.co/" + (base + "/" if base else ""))
    return prefix + quote(name, safe="/")


def _sanitize(item: Any, kind: str) -> dict | None:
    """Allow-list public identifiers, timestamps and bounded metadata only."""
    if getattr(item, "private",None) is not False:
        return None
    name = getattr(item, "id", None)
    if not isinstance(name, str) or "/" not in name:
        return None
    org, tail = name.split("/", 1)
    if org != ORG or _ALLOWED_NAME.fullmatch(tail) is None:
        return None
    sha = getattr(item, "sha", None)
    sha = sha if isinstance(sha, str) and _HEX40.fullmatch(sha) else None
    tags = getattr(item, "tags", None)
    tags = tags if isinstance(tags, (list, tuple)) else []
    tags = [tag for tag in tags if isinstance(tag, str)
            and 0 < len(tag) <= 80 and "\n" not in tag][:12]
    last_modified = getattr(item, "last_modified", None)
    stamp = str(last_modified) if last_modified is not None else None
    if stamp and len(stamp) > 48:
        stamp = None
    sdk = getattr(item, "sdk", None)
    sdk = sdk if kind == "space" and isinstance(sdk, str) and len(sdk) <= 30 else None
    return {
        "id": f"{kind}:{name}",
        "hub_id": name,
        "label": tail,
        "kind": kind,
        "url": _asset_url(kind, name),
        "source_revision": sha,
        "last_modified": stamp,
        "sdk": sdk,
        "tags": tags,
        "evidence_state": "PUBLIC_HUB_METADATA",
        "execution_authorized": False,
        "operational_readiness": "NOT_EVALUATED",
        "verticals": [],
    }


def _topology(path: Path) -> tuple[list[dict], str | None]:
    """Read dated canonical topology without trusting its asset existence."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if type(doc) is not dict or type(doc.get("verticals")) is not list:
        raise AtlasError("VERTICAL_TOPOLOGY_INVALID")
    stamp = doc.get("generated")
    stamp = stamp if isinstance(stamp, str) and len(stamp) <= 40 else None
    verticals = []
    seen = set()
    for item in doc["verticals"]:
        if type(item) is not dict:
            raise AtlasError("VERTICAL_RECORD_INVALID")
        vid = item.get("id")
        name = item.get("name")
        if (not isinstance(vid, str) or not _ALLOWED_NAME.fullmatch(vid)
                or not isinstance(name, str) or not 0 < len(name) <= 96
                or vid in seen):
            raise AtlasError("VERTICAL_IDENTITY_INVALID")
        seen.add(vid)
        relations = {}
        for kind in _TIERS:
            key = {"space": "spaces", "model": "models", "dataset": "datasets"}[kind]
            values = item.get(key, [])
            if not isinstance(values, list):
                raise AtlasError("VERTICAL_LINK_SET_INVALID")
            # Do not emit or preserve unmatched (possibly private) references.
            relations[kind] = {
                v if "/" in v else f"{ORG}/{v}"
                for v in values if isinstance(v, str) and len(v) <= 150
            }
        domain = item.get("domain")
        verticals.append({
            "id": "vertical:" + vid,
            "vertical_id": vid,
            "name": name,
            "domain": domain if isinstance(domain, str) and len(domain) <= 120 else "",
            "state": "DECLARED_DATED_TOPOLOGY",
            "relations": relations,
        })
    return verticals, stamp


def collect(*, lister: Callable[[str, int], list[Any]] | None = None,
            topology_path: Path | None = None,
            now: datetime | None = None) -> dict:
    """Fresh, bounded, completely public snapshot. Never mixes partial data."""
    if lister is None:
        from huggingface_hub import HfApi
        api = HfApi(token=False)
        def lister(kind: str, limit: int) -> list[Any]:
            fn = {"space": api.list_spaces,
                  "model": api.list_models,
                  "dataset": api.list_datasets}[kind]
            return list(fn(author=ORG, limit=limit, full=True, token=False))
    topo, topology_stamp = _topology(topology_path or ROOT / "verticals.json")
    output = {}
    # Three independent API calls run concurrently. A partial failure denies
    # the entire graph, rather than silently turning it into a complete estate.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {kind: pool.submit(lister, kind, _limits[kind]) for kind in _TIERS}
        for kind, future in futures.items():
            candidates = future.result()
            if type(candidates) is not list or len(candidates) >= _limits[kind]:
                raise AtlasError("INCOMPLETE_PUBLIC_LIST_" + kind.upper())
            clean = [_sanitize(item, kind) for item in candidates]
            values = sorted((x for x in clean if x is not None), key=lambda x:x["hub_id"])
            if len({x["id"] for x in values}) != len(values):
                raise AtlasError("DUPLICATE_PUBLIC_ID")
            output[kind] = values
    nodes = [x for kind in _TIERS for x in output[kind]]
    lookup = {node["id"]: node for node in nodes}
    links = []
    vertical_rows = []
    for vertical in topo:
        v_id = vertical["id"]
        matched = []
        for kind in _TIERS:
            for hub_id in sorted(vertical["relations"][kind]):
                node = lookup.get(kind + ":" + hub_id)
                if node is None:
                    continue
                if vertical["vertical_id"] not in node["verticals"]:
                    node["verticals"].append(vertical["vertical_id"])
                matched.append(node["id"])
                links.append({
                    "source": v_id, "target": node["id"],
                    "kind": "DECLARED_MEMBERSHIP_MATCHED_TO_PUBLIC_HUB",
                    "evidence_state": "DATED_TOPOLOGY_NOT_RUNTIME_EDGE",
                })
        vertical_rows.append({
            "id": v_id, "vertical_id": vertical["vertical_id"],
            "label": vertical["name"], "domain": vertical["domain"],
            "kind": "vertical", "evidence_state": vertical["state"],
            "members_public": len(set(matched)),
            "execution_authorized": False,
        })
    for node in nodes:
        node["verticals"].sort()
    counts = {kind:len(output[kind]) for kind in _TIERS}
    body = {
        "schema": SCHEMA,
        "state": "OBSERVED_PUBLIC_HUB_METADATA",
        "scope": "ANONYMOUS_PUBLIC_HUB_ONLY",
        "observed_at": _utc(now),
        "expires_after_seconds": CACHE_SECONDS,
        "org": ORG,
        "counts": counts,
        "declared_verticals": len(vertical_rows),
        "topology_generated_at": topology_stamp,
        "topology_state": "HISTORICAL_DECLARED_RELATIONSHIPS",
        "nodes": vertical_rows + nodes,
        "links": links,
        "private_assets_excluded": True,
        "source_byte_attestation": "NOT_EVALUATED",
        "runtime_readiness": "NOT_EVALUATED",
        "production_qualified": False,
        "execution_authorized": False,
        "limits": [
            "Public Hugging Face metadata is observed, not a verified deployment or model quality score.",
            "Only relations explicitly named in the dated vertical registry and visible in public metadata are drawn.",
            "Nonpublic resources are never emitted or counted in this public response.",
            "No model weights or dataset rows were downloaded and no training was performed.",
            "The SHA-256 fingerprint detects changed bytes, not origin authentication.",
        ],
    }
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False,
                         ensure_ascii=False).encode("utf-8")
    body["observation_sha256"] = hashlib.sha256(payload).hexdigest()
    return body


def cached_public_atlas() -> dict:
    global _cache
    with _cache_lock:
        now = time.monotonic()
        if _cache is not None and now < _cache[0]:
            return _cache[1]
        # Never serve expired cache as live data after a failed refresh.
        result = collect()
        _cache = (time.monotonic() + CACHE_SECONDS, result)
        return result
