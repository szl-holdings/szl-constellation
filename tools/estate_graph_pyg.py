# SPDX-License-Identifier: Apache-2.0
"""CPU validator for the szl-estate-graph PyG job spec.

Does not import PyTorch or PyG, does not build a container, and does not
launch. The spec stays non-dispatchable while its image digest is UNKNOWN.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

SCHEMA = "szl.estate-graph.pyg-admission/v0"
SPEC_RELATIVE = Path("datasets/szl-estate-graph/pyg-jobspec.v0.json")
NODES_RELATIVE = Path("datasets/szl-estate-graph/nodes.csv")
EDGES_RELATIVE = Path("datasets/szl-estate-graph/edges.csv")
GRAPH_RELATIVE = Path("datasets/szl-estate-graph/graph.json")
LAUNCHER = "saywa"
PROVIDERS = ["massed", "salad"]
USD_TO_UUSD = 1_000_000
CAPS = {
    "perRunUsd": 100,
    "perDayUsd": 500,
    "perMonthUsd": 5000,
    "perRunUusd": 100 * USD_TO_UUSD,
    "perDayUusd": 500 * USD_TO_UUSD,
    "perMonthUusd": 5000 * USD_TO_UUSD,
}
FORBIDDEN_IMAGE_MARKERS = ("nvcr.io", "ngc.nvidia.com", "nvidia-ai-enterprise")


class SpecError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _counts(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        kind = row[field]
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def validate(root: Path) -> dict[str, Any]:
    spec_path = root / SPEC_RELATIVE
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("schema") != "szl.estate-graph.pyg-job/v0":
        raise SpecError("SCHEMA")
    if spec.get("launch") is not False:
        raise SpecError("LAUNCH_REFUSED")
    if spec.get("launcher") != LAUNCHER:
        raise SpecError("LAUNCHER_NOT_SAYWA")
    if spec.get("providers") != PROVIDERS:
        raise SpecError("PROVIDER_NOT_ALLOWED")
    if spec.get("caps") != CAPS:
        raise SpecError("CAP_MISMATCH")
    container = spec.get("container")
    if type(container) is not dict:
        raise SpecError("CONTAINER")
    if container.get("forbiddenRegistries") != list(FORBIDDEN_IMAGE_MARKERS[:2]):
        raise SpecError("REGISTRY_DENYLIST")
    image_text = " ".join(
        str(container.get(field) or "") for field in ("plannedBase", "digest", "image")
    ).lower()
    for marker in FORBIDDEN_IMAGE_MARKERS:
        if marker in image_text:
            raise SpecError("ENTERPRISE_IMAGE_FORBIDDEN")
    if container.get("digest") != "UNKNOWN" or container.get("status") != "NOT_BUILT":
        raise SpecError("IMAGE_NOT_BUILT")
    if container.get("mutableTagForbidden") is not True:
        raise SpecError("MUTABLE_TAG")
    nodes = _rows(root / NODES_RELATIVE)
    edges = _rows(root / EDGES_RELATIVE)
    node_ids = [row["id"] for row in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise SpecError("NODE_ID_DUPLICATE")
    id_set = set(node_ids)
    for edge in edges:
        if edge["source"] not in id_set or edge["target"] not in id_set:
            raise SpecError("EDGE_ENDPOINT")
    graph = json.loads((root / GRAPH_RELATIVE).read_text(encoding="utf-8"))
    if graph.get("schema") != "szl.estate-graph/v1":
        raise SpecError("GRAPH_SCHEMA")
    node_kinds = _counts(nodes, "kind")
    edge_kinds = _counts(edges, "kind")
    declared = spec.get("graph")
    if type(declared) is not dict:
        raise SpecError("GRAPH_DECLARATION")
    if declared.get("nodeCount") != len(nodes) or declared.get("edgeCount") != len(edges):
        raise SpecError("GRAPH_COUNT")
    if declared.get("nodeKinds") != node_kinds or declared.get("edgeKinds") != edge_kinds:
        raise SpecError("GRAPH_KINDS")
    return {
        "schema": SCHEMA,
        "launchAuthorized": False,
        "trainingStarted": False,
        "imagePushed": False,
        "launcher": LAUNCHER,
        "launcherImplementation": "UNKNOWN",
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "nodeKinds": node_kinds,
        "edgeKinds": edge_kinds,
        "reasons": ["IMAGE_NOT_BUILT", "AMARU_LICENSE_CHECK_PENDING"],
    }
