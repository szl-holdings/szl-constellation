#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Dependency-free structural verifier for the Constellation runtime source."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPACE = ROOT / "space"

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
        "listener": listener,
        "managedFileCount": len(managed_files),
        "managedFilesSha256": digests,
    }


def main() -> int:
    print(json.dumps(verify(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
