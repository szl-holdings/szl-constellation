#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Dependency-free structural verifier for the Constellation runtime source."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

from constellation_targets import PRODUCTION, STAGING, TARGETS

ROOT = Path(__file__).resolve().parents[1]
SPACE = ROOT / "space"
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "publish-constellation-space.yml"
CREDENTIAL_SELECTOR_REVISION = "bedcd3c77b5cf745dcc1490ac503e30397633227"

RUNTIME_REQUIREMENTS = (
    "gradio",
    "fastapi",
    "uvicorn",
    "pydantic",
)
TEST_REQUIREMENTS = ("pytest", "httpx")
REQUIRED_RUNTIME_FILES = (
    ".gitattributes",
    "README.md",
    "app.py",
    "c2/index.html",
    "crosscheck.py",
    "estates.json",
    "holo/index.html",
    "requirements.txt",
    "test_runtime_contract.py",
    "tests/test_app.py",
    "verticals.json",
)


def exact_pins(path: Path, expected_names: tuple[str, ...]) -> dict[str, str]:
    rows = [
        row.strip()
        for row in path.read_text(encoding="utf-8").splitlines()
        if row.strip() and not row.lstrip().startswith("#")
    ]
    pattern = re.compile(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)")
    pins: dict[str, str] = {}
    for row in rows:
        match = pattern.fullmatch(row)
        if match is None:
            raise AssertionError(f"non-exact dependency in {path}: {row!r}")
        name = match.group(1).lower().replace("_", "-")
        if name in pins:
            raise AssertionError(f"duplicate dependency in {path}: {name}")
        pins[name] = match.group(2)
    normalized = tuple(name.lower().replace("_", "-") for name in expected_names)
    if tuple(pins) != normalized:
        raise AssertionError(
            f"dependency order/set drift in {path}: expected={normalized!r} observed={tuple(pins)!r}"
        )
    return pins


def read_front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError("README front matter missing")
    try:
        block = text.split("---\n", 2)[1]
    except IndexError as exc:
        raise AssertionError("README front matter is not closed") from exc
    values: dict[str, str] = {}
    for row in block.splitlines():
        if not row or row.startswith(" ") or ":" not in row:
            continue
        key, value = row.split(":", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def listener_contract(path: Path) -> dict[str, int | bool]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    uvicorn_calls = 0
    launch_calls = 0
    mounted_ssr_disabled = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value.id if isinstance(node.func.value, ast.Name) else None
        if owner == "uvicorn" and node.func.attr == "run":
            uvicorn_calls += 1
        if node.func.attr == "launch":
            launch_calls += 1
        if owner == "gr" and node.func.attr == "mount_gradio_app":
            for keyword in node.keywords:
                if (
                    keyword.arg == "ssr_mode"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is False
                ):
                    mounted_ssr_disabled += 1
    valid = (uvicorn_calls, launch_calls, mounted_ssr_disabled) == (1, 0, 1)
    return {
        "valid": valid,
        "uvicornRunCalls": uvicorn_calls,
        "launchCalls": launch_calls,
        "mountsWithSsrDisabled": mounted_ssr_disabled,
    }


def target_selection_lines() -> tuple[str, ...]:
    """The exact workflow lines that map the dispatch input onto one target.

    Derived from ``constellation_targets.TARGETS`` so the workflow, the
    publisher and this verifier cannot disagree about ids or lock keys.
    """

    staging = "github.event_name == 'workflow_dispatch' && inputs.target == 'staging'"
    return (
        "concurrency:\n"
        "      group: ${{ "
        f"{staging} && '{TARGETS[STAGING].lock_group}' || '{TARGETS[PRODUCTION].lock_group}'"
        " }}\n"
        "      cancel-in-progress: false\n",
        f"CONSTELLATION_TARGET: ${{{{ {staging} && '{STAGING}' || '{PRODUCTION}' }}}}",
        "TARGET_SPACE: ${{ "
        f"{staging} && '{TARGETS[STAGING].space_id}' || '{TARGETS[PRODUCTION].space_id}'"
        " }}",
    )


def publisher_credential_contract(path: Path) -> dict[str, object]:
    """Prove the publisher selects and transports credentials fail-closed."""

    text = path.read_text(encoding="utf-8")
    required = (
        "id-token: write",
        "repository: szl-holdings/.github",
        f"ref: {CREDENTIAL_SELECTOR_REVISION}",
        ".shared-github/.github/scripts/acquire_hf_publisher_token.py",
        '--target-repo "${TARGET_SPACE}"',
        "--target-type space",
        '--oidc-resource "spaces/${TARGET_SPACE}"',
        *target_selection_lines(),
        '--token-file "${RUNNER_TEMP}/constellation-hf-token"',
        "HF_ORG_TOKEN_CANDIDATE",
        "HF_ORG_TOKEN1_CANDIDATE",
        "HF_WRITE_TOKEN_CANDIDATE",
        "HF_TOKEN_CANDIDATE",
        "HUGGINGFACE_TOKEN_CANDIDATE",
        "HUGGING_FACE_HUB_TOKEN_CANDIDATE",
        'token_file="${RUNNER_TEMP}/constellation-hf-token"',
        "HF_TOKEN=\"$(tr -d '\\r\\n' < \"$token_file\")\"",
        "python tools/run_publish_constellation.py",
        "artifacts/constellation-publisher-credential.json",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise AssertionError(f"publisher credential contract missing markers: {missing}")
    forbidden = (
        "HF_TOKEN: ${{ secrets.HF_TOKEN }}",
        "--allow-create",
        "echo $HF_TOKEN",
        "set -x",
    )
    present = [marker for marker in forbidden if marker in text]
    if present:
        raise AssertionError(f"publisher credential contract contains forbidden markers: {present}")
    if text.count("acquire_hf_publisher_token.py") != 1:
        raise AssertionError("publisher must use exactly one credential selector invocation")
    if text.count("run_publish_constellation.py") != 3:
        raise AssertionError(
            "publisher entrypoint must appear once in paths, once in compilation, and once in the scoped publish step"
        )
    if re.search(r"^concurrency:", text, flags=re.MULTILINE):
        raise AssertionError(
            "publisher lock must be the per-asset job lock, not a workflow-wide group"
        )
    named = set(re.findall(r"SZLHOLDINGS/[A-Za-z0-9._-]+", text))
    allowed = {target.space_id for target in TARGETS.values()}
    if named != allowed:
        raise AssertionError(
            f"publisher workflow names Hub ids outside its targets: {sorted(named - allowed)} "
            f"or omits {sorted(allowed - named)}"
        )
    return {
        "valid": True,
        "trustedPublisherRequested": True,
        "fallbackCandidateCount": 6,
        "selectorRevision": CREDENTIAL_SELECTOR_REVISION,
        "tokenTransport": "RESTRICTED_EPHEMERAL_FILE",
        "jobEnvironmentExported": False,
        "defaultTarget": PRODUCTION,
        "targets": {
            name: {
                "spaceId": target.space_id,
                "visibility": target.visibility,
                "lock": target.lock_group,
                "oidcResource": target.oidc_resource,
            }
            for name, target in sorted(TARGETS.items())
        },
    }


def space_identity_contract(path: Path) -> dict[str, object]:
    """The runtime's allowlisted Space ids and hosts equal the publisher targets."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    declared: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = node.targets[0]
            if isinstance(name, ast.Name) and name.id in {"KNOWN_SPACE_HOSTS", "DEFAULT_SPACE_ID"}:
                declared[name.id] = ast.literal_eval(node.value)
    expected_hosts = {target.space_id: target.live_host for target in TARGETS.values()}
    if declared.get("KNOWN_SPACE_HOSTS") != expected_hosts:
        raise AssertionError(
            f"app.py KNOWN_SPACE_HOSTS drifted from publisher targets: {declared.get('KNOWN_SPACE_HOSTS')!r}"
        )
    if declared.get("DEFAULT_SPACE_ID") != TARGETS[PRODUCTION].space_id:
        raise AssertionError("app.py DEFAULT_SPACE_ID must be the production Space")
    return {"valid": True, "knownSpaceHosts": expected_hosts}


def verify() -> dict[str, object]:
    missing = [relative for relative in REQUIRED_RUNTIME_FILES if not (SPACE / relative).is_file()]
    if missing:
        raise AssertionError(f"required runtime files missing: {missing}")

    runtime_pins = exact_pins(SPACE / "requirements.txt", RUNTIME_REQUIREMENTS)
    test_pins = exact_pins(SPACE / "requirements-test.txt", TEST_REQUIREMENTS)
    publish_pins = exact_pins(
        ROOT / "tools" / "requirements-publish.txt", ("huggingface_hub",)
    )
    metadata = read_front_matter(SPACE / "README.md")
    if metadata.get("sdk") != "gradio":
        raise AssertionError(f"unexpected Space SDK: {metadata.get('sdk')!r}")
    if metadata.get("app_file") != "app.py":
        raise AssertionError(f"unexpected Space app_file: {metadata.get('app_file')!r}")
    if metadata.get("python_version") != "3.13":
        raise AssertionError(
            f"unexpected Space Python version: {metadata.get('python_version')!r}"
        )
    if metadata.get("sdk_version") != runtime_pins["gradio"]:
        raise AssertionError(
            "README sdk_version and exact Gradio dependency are not identical"
        )

    listener = listener_contract(SPACE / "app.py")
    if not listener["valid"]:
        raise AssertionError(f"single-listener contract failed: {listener}")

    publisher = publisher_credential_contract(PUBLISH_WORKFLOW)
    identity = space_identity_contract(SPACE / "app.py")

    app_text = (SPACE / "app.py").read_text(encoding="utf-8")
    for route in (
        '"/healthz"',
        '"/readyz"',
        '"/api/source"',
        '"/api/constellation/manifest"',
        '"/api/panels/status"',
    ):
        if route not in app_text:
            raise AssertionError(f"required public contract route missing: {route}")

    managed_files = sorted(
        path.relative_to(SPACE).as_posix()
        for path in SPACE.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    digests = {
        relative: hashlib.sha256((SPACE / relative).read_bytes()).hexdigest()
        for relative in managed_files
    }
    return {
        "state": "CONSTELLATION_SOURCE_VERIFIED",
        "sdk": metadata["sdk"],
        "sdkVersion": metadata["sdk_version"],
        "pythonVersion": metadata["python_version"],
        "runtimePins": runtime_pins,
        "testPins": test_pins,
        "publisherPins": publish_pins,
        "publisherCredentialContract": publisher,
        "spaceIdentity": identity,
        "listener": listener,
        "managedFileCount": len(managed_files),
        "managedFilesSha256": digests,
    }


def main() -> int:
    print(json.dumps(verify(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
