# SPDX-License-Identifier: Apache-2.0
"""Strict local loader for the archive-revival lineage registry."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Final

HERE: Final = Path(__file__).resolve().parent
REGISTRY_PATH: Final = HERE / "registry.json"
NAME_RE: Final = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
DISPOSITIONS: Final = {"SOURCE_OWNER", "CONSOLIDATE", "HISTORICAL"}
EXPECTED_COUNTS: Final = {"source_owner": 4, "consolidate": 24, "historical": 6, "total": 34}


class RegistryError(ValueError):
    """The source-controlled lineage registry violates its schema contract."""


def duplicate_guard(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise RegistryError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def reject_constant(value: str) -> None:
    raise RegistryError(f"non-finite JSON constant: {value}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def receipt(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise RegistryError(f"{label} key mismatch: missing={missing}, extra={extra}")


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    try:
        registry = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=duplicate_guard,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"registry unavailable: {type(exc).__name__}") from exc
    if not isinstance(registry, dict):
        raise RegistryError("registry root must be an object")
    _exact_keys(
        registry,
        {"schema", "contract", "truth_boundary", "counts", "repositories"},
        "registry",
    )
    if registry["schema"] != "szl.archive-revival-registry/v2":
        raise RegistryError("unexpected registry schema")
    contract = registry["contract"]
    if not isinstance(contract, dict):
        raise RegistryError("contract must be an object")
    _exact_keys(contract, {"repository", "path", "merge_sha", "authority"}, "contract")
    if contract["repository"] != "szl-holdings/.github":
        raise RegistryError("contract repository drifted")
    if contract["path"] != "governance/archive-portfolio-v2.json":
        raise RegistryError("contract path drifted")
    if not isinstance(contract["merge_sha"], str) or not SHA_RE.fullmatch(contract["merge_sha"]):
        raise RegistryError("contract merge_sha must be an exact lowercase commit SHA")
    if registry["counts"] != EXPECTED_COUNTS:
        raise RegistryError("declared counts do not match the v2 contract")
    expected_truth = [
        "CLASSIFIED",
        "UNARCHIVED",
        "SOURCE_PR",
        "MERGED",
        "HUB_PUBLISHED",
        "RUNTIME_READY",
        "EXACT_READBACK_VERIFIED",
    ]
    if registry["truth_boundary"] != expected_truth:
        raise RegistryError("truth boundary order drifted")
    rows = registry["repositories"]
    if not isinstance(rows, list) or len(rows) != EXPECTED_COUNTS["total"]:
        raise RegistryError("repository row count must be exactly 34")

    names: set[str] = set()
    counts = {"SOURCE_OWNER": 0, "CONSOLIDATE": 0, "HISTORICAL": 0}
    row_keys = {
        "name",
        "disposition",
        "successor",
        "capability",
        "showcase",
        "expected_archived",
        "immutable_history",
        "provider_state",
    }
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RegistryError(f"repository row {index} must be an object")
        _exact_keys(row, row_keys, f"repository row {index}")
        name = row["name"]
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise RegistryError(f"invalid repository name at row {index}")
        if name in names:
            raise RegistryError(f"duplicate repository row: {name}")
        names.add(name)
        disposition = row["disposition"]
        if disposition not in DISPOSITIONS:
            raise RegistryError(f"invalid disposition for {name}")
        counts[disposition] += 1
        if not isinstance(row["capability"], str) or not row["capability"].strip():
            raise RegistryError(f"capability unavailable for {name}")
        if not isinstance(row["showcase"], list) or not row["showcase"]:
            raise RegistryError(f"showcase list unavailable for {name}")
        if any(not isinstance(item, str) or not item.startswith("SZLHOLDINGS/") for item in row["showcase"]):
            raise RegistryError(f"invalid showcase identity for {name}")
        if row["provider_state"] != "UNAVAILABLE_NOT_MEASURED":
            raise RegistryError(f"local registry cannot claim provider evidence for {name}")
        if disposition == "SOURCE_OWNER":
            if row["successor"] != name or row["expected_archived"] is not False or row["immutable_history"] is not False:
                raise RegistryError(f"source-owner invariant failed for {name}")
        elif disposition == "CONSOLIDATE":
            if not isinstance(row["successor"], str) or not row["successor"]:
                raise RegistryError(f"successor unavailable for {name}")
            if row["expected_archived"] is not True or row["immutable_history"] is not False:
                raise RegistryError(f"consolidation invariant failed for {name}")
        else:
            if row["successor"] is not None or row["expected_archived"] is not True or row["immutable_history"] is not True:
                raise RegistryError(f"historical invariant failed for {name}")

    if counts != {"SOURCE_OWNER": 4, "CONSOLIDATE": 24, "HISTORICAL": 6}:
        raise RegistryError(f"computed disposition counts drifted: {counts}")
    restored = sorted(name for name in names if next(row for row in rows if row["name"] == name)["disposition"] == "SOURCE_OWNER")
    if restored != ["szl-atelier", "szl-mesh", "szl-router", "uds-bundles"]:
        raise RegistryError(f"source-owner allowlist drifted: {restored}")
    return registry


def public_registry() -> dict[str, Any]:
    """Return the validated registry and a deterministic local receipt."""

    registry = load_registry()
    value = dict(registry)
    value["receipt_sha256"] = receipt(registry)
    value["provider_readback"] = "UNAVAILABLE_NOT_PERFORMED"
    return value


def resolve_repository(name: str) -> dict[str, Any] | None:
    if not NAME_RE.fullmatch(name):
        return None
    registry = load_registry()
    return next((row for row in registry["repositories"] if row["name"] == name), None)
