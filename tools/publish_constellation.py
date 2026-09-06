#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish protected-main Constellation source and prove the live runtime.

GitHub protected main is the sole writer. The publisher commits the exact
``space/`` tree plus a source-binding receipt to the fixed Hugging Face Space,
waits for the provider source and runtime revisions to converge, verifies every
immutable file byte, then exercises the public FastAPI/Gradio contracts.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

from verify_constellation import verify as verify_source

ROOT = Path(__file__).resolve().parents[1]
SPACE_ROOT = ROOT / "space"
SPACE_ID = "SZLHOLDINGS/szl-constellation"
REPO_TYPE = "space"
LIVE_BASE = "https://szlholdings-szl-constellation.hf.space"
EXPECTED_REPOSITORY = "szl-holdings/szl-constellation"
EXPECTED_HARDWARE = "cpu-basic"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
SHA40 = re.compile(r"[0-9a-f]{40}")


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"required environment variable absent: {name}")
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def bounded_read(response: Any, limit: int = MAX_RESPONSE_BYTES) -> bytes:
    data = response.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError(f"response exceeded {limit} bytes")
    return data


def request_bytes(url: str, *, timeout: int = 30) -> tuple[int, str, bytes]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "szl-constellation-publisher/1.0",
            "Accept": "*/*",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return (
                int(response.status),
                str(response.headers.get("Content-Type") or ""),
                bounded_read(response),
            )
    except urllib.error.HTTPError as error:
        return (
            int(error.code),
            str(error.headers.get("Content-Type") or ""),
            bounded_read(error),
        )


def request_json(url: str, *, timeout: int = 30) -> dict[str, Any]:
    status, content_type, data = request_bytes(url, timeout=timeout)
    if status != 200:
        raise RuntimeError(f"expected HTTP 200 from {url}, observed {status}")
    if "json" not in content_type.lower():
        raise RuntimeError(f"expected JSON from {url}, observed {content_type!r}")
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object from {url}")
    return payload


def current_protected_main(repository: str, token: str) -> str:
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    request = urllib.request.Request(
        f"{api_url}/repos/{repository}/commits/main",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "szl-constellation-publisher/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    revision = str(payload.get("sha") or "").lower()
    if SHA40.fullmatch(revision) is None:
        raise RuntimeError("protected-main revision unavailable")
    return revision


def source_files(root: Path) -> list[Path]:
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )
    if not files:
        raise RuntimeError("no Constellation runtime files found")
    return files


def tree_digest(files: dict[str, dict[str, Any]]) -> str:
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def stage_tree(source_revision: str, workflow_run_id: str) -> tuple[Path, tempfile.TemporaryDirectory[str], dict[str, dict[str, Any]]]:
    holder: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory(
        prefix="constellation-publish-"
    )
    stage = Path(holder.name)
    shutil.copytree(SPACE_ROOT, stage, dirs_exist_ok=True)
    for cache in list(stage.rglob("__pycache__")):
        shutil.rmtree(cache)
    for compiled in list(stage.rglob("*.py[co]")):
        compiled.unlink()

    managed: dict[str, dict[str, Any]] = {}
    for path in source_files(stage):
        relative = path.relative_to(stage).as_posix()
        data = path.read_bytes()
        managed[relative] = {
            "bytes": len(data),
            "sha256": sha256_bytes(data),
        }

    binding = {
        "schema": "szl.github-to-huggingface-source/v1",
        "state": "SOURCE_BOUND_PUBLICATION",
        "source": {
            "repository": EXPECTED_REPOSITORY,
            "revision": source_revision,
            "path": "space",
            "relation": "protected-main-canonical-publisher",
        },
        "destination": {
            "repoId": SPACE_ID,
            "repoType": REPO_TYPE,
            "visibility": "public",
            "hardware": EXPECTED_HARDWARE,
        },
        "workflow": {
            "runId": workflow_run_id,
            "runAttempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        },
        "managedFiles": managed,
        "managedTreeSha256": tree_digest(managed),
        "limits": [
            "The immutable Hub revision is established after this receipt is committed.",
            "Byte equality establishes source identity, not model quality, safety, or business performance.",
            "The public scenario plane is synthetic and has no effector authority.",
        ],
    }
    binding_path = stage / "szl-source-binding.json"
    binding_path.write_text(
        json.dumps(binding, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return stage, holder, managed


def runtime_state(api: HfApi) -> dict[str, Any]:
    runtime = api.get_space_runtime(repo_id=SPACE_ID)
    raw = getattr(runtime, "raw", None)
    if not isinstance(raw, dict):
        raw = {}
    hardware = raw.get("hardware") if isinstance(raw.get("hardware"), dict) else {}
    replicas = raw.get("replicas") if isinstance(raw.get("replicas"), dict) else {}
    domains = raw.get("domains") if isinstance(raw.get("domains"), list) else []
    return {
        "stage": str(getattr(runtime, "stage", "UNKNOWN") or "UNKNOWN").upper(),
        "sourceRevision": str(raw.get("sha") or "").lower(),
        "hardwareCurrent": hardware.get("current", getattr(runtime, "hardware", None)),
        "hardwareRequested": hardware.get(
            "requested", getattr(runtime, "requested_hardware", None)
        ),
        "replicasCurrent": replicas.get("current"),
        "replicasRequested": replicas.get("requested"),
        "domainReady": any(
            isinstance(item, dict)
            and item.get("domain") == "szlholdings-szl-constellation.hf.space"
            and item.get("stage") == "READY"
            for item in domains
        ),
    }


def wait_for_runtime(api: HfApi, target_revision: str, timeout_seconds: int = 1200) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] = {}
    restarted = False
    while time.monotonic() < deadline:
        info = api.repo_info(repo_id=SPACE_ID, repo_type=REPO_TYPE)
        last = runtime_state(api)
        last["repoRevision"] = str(getattr(info, "sha", "") or "").lower()
        last["private"] = bool(getattr(info, "private", False))
        print(json.dumps({"providerObservation": last}, sort_keys=True), flush=True)
        if last["private"]:
            raise RuntimeError("destination Space became private")
        if (
            last["repoRevision"] == target_revision
            and last["sourceRevision"] == target_revision
            and last["stage"] == "RUNNING"
            and last["hardwareCurrent"] == EXPECTED_HARDWARE
            and last["hardwareRequested"] == EXPECTED_HARDWARE
            and last["replicasCurrent"] == 1
            and last["replicasRequested"] == 1
            and last["domainReady"] is True
        ):
            return last
        if (
            last["repoRevision"] == target_revision
            and last["stage"] in {"PAUSED", "SLEEPING", "STOPPED"}
            and not restarted
        ):
            api.restart_space(repo_id=SPACE_ID, factory_reboot=False)
            restarted = True
        if last["stage"] in {"BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"}:
            raise RuntimeError(f"provider runtime failed closed: {last}")
        time.sleep(10)
    raise TimeoutError(f"provider did not converge on {target_revision}: {last}")


def immutable_bytes(revision: str, relative: str) -> bytes:
    encoded = urllib.parse.quote(relative, safe="/")
    url = (
        f"https://huggingface.co/spaces/{SPACE_ID}/resolve/{revision}/{encoded}"
        "?download=true"
    )
    status, _content_type, data = request_bytes(url, timeout=60)
    if status != 200:
        raise RuntimeError(f"immutable file unavailable: {relative} status={status}")
    return data


def verify_immutable_tree(
    api: HfApi,
    stage: Path,
    target_revision: str,
) -> dict[str, dict[str, Any]]:
    desired = {
        path.relative_to(stage).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in source_files(stage)
    }
    observed_paths = set(
        api.list_repo_files(
            repo_id=SPACE_ID,
            repo_type=REPO_TYPE,
            revision=target_revision,
        )
    )
    if observed_paths != set(desired):
        raise RuntimeError(
            "provider tree differs from canonical stage: "
            f"missing={sorted(set(desired) - observed_paths)} "
            f"extra={sorted(observed_paths - set(desired))}"
        )
    for relative, expected in desired.items():
        data = immutable_bytes(target_revision, relative)
        observed = {"bytes": len(data), "sha256": sha256_bytes(data)}
        if observed != expected:
            raise RuntimeError(
                f"immutable byte mismatch for {relative}: expected={expected} observed={observed}"
            )
    return desired


def verify_live(target_revision: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(36):
        try:
            status_root, type_root, root = request_bytes(LIVE_BASE + "/", timeout=45)
            status_c2, _type_c2, c2 = request_bytes(LIVE_BASE + "/c2", timeout=45)
            status_panels, _type_panels, panels = request_bytes(
                LIVE_BASE + "/panels", timeout=45
            )
            health = request_json(LIVE_BASE + "/healthz", timeout=45)
            ready = request_json(LIVE_BASE + "/readyz", timeout=45)
            source = request_json(LIVE_BASE + "/api/source", timeout=45)
            panel_status = request_json(
                LIVE_BASE + "/api/panels/status", timeout=45
            )
            manifest = request_json(
                LIVE_BASE + "/api/constellation/manifest", timeout=45
            )

            if status_root != 200 or "html" not in type_root.lower():
                raise AssertionError(f"root surface unavailable: {status_root} {type_root}")
            if b"SZL CONSTELLATION" not in root.upper():
                raise AssertionError("root identity absent")
            if status_c2 != 200 or not c2:
                raise AssertionError(f"C2 surface unavailable: {status_c2}")
            if status_panels != 200 or not panels:
                raise AssertionError(f"panel surface unavailable: {status_panels}")
            if health.get("ok") is not True:
                raise AssertionError(f"health contract not ready: {health}")
            if ready.get("ready") is not True:
                raise AssertionError(f"readiness contract not ready: {ready}")
            checks = ready.get("checks")
            if not isinstance(checks, dict) or not checks or not all(checks.values()):
                raise AssertionError(f"readiness checks not all true: {checks}")
            if source.get("state") != "MEASURED":
                raise AssertionError(f"source state is not measured: {source}")
            if source.get("source_revision") != target_revision:
                raise AssertionError(
                    "live source revision mismatch: "
                    f"expected={target_revision} observed={source.get('source_revision')}"
                )
            if source.get("app_bytes_match") is not True:
                raise AssertionError(f"live app byte binding failed: {source}")
            if source.get("provider_stage") != "RUNNING":
                raise AssertionError(f"live provider stage mismatch: {source}")
            if panel_status.get("panels") != "MOUNTED":
                raise AssertionError(f"panel mount not available: {panel_status}")
            if manifest.get("state") != "DECLARED":
                raise AssertionError(f"manifest state drift: {manifest}")

            return {
                "attempt": attempt + 1,
                "root": {"status": status_root, "contentType": type_root},
                "c2": {"status": status_c2, "bytesObserved": len(c2)},
                "panels": {"status": status_panels, "bytesObserved": len(panels)},
                "health": health,
                "ready": ready,
                "source": source,
                "panelStatus": panel_status,
                "manifestState": manifest.get("state"),
            }
        except Exception as error:  # retry during edge/runtime propagation
            last_error = error
            print(
                json.dumps(
                    {
                        "liveAttempt": attempt + 1,
                        "state": "NOT_READY",
                        "error": type(error).__name__,
                        "detail": str(error)[:300],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            time.sleep(10)
    raise TimeoutError(f"live contract did not converge: {last_error}")


def publish() -> dict[str, Any]:
    hf_token = required_env("HF_TOKEN")
    github_token = required_env("GITHUB_TOKEN")
    source_revision = required_env("GITHUB_SHA").lower()
    workflow_run_id = required_env("GITHUB_RUN_ID")
    repository = required_env("GITHUB_REPOSITORY")
    if repository != EXPECTED_REPOSITORY:
        raise RuntimeError(f"unexpected GitHub repository: {repository}")
    if SHA40.fullmatch(source_revision) is None:
        raise RuntimeError(f"invalid GitHub source revision: {source_revision!r}")
    protected_main = current_protected_main(repository, github_token)
    if protected_main != source_revision:
        raise RuntimeError(
            f"publisher source is not current protected main: source={source_revision} main={protected_main}"
        )

    local_verification = verify_source()
    stage, holder, source_managed = stage_tree(source_revision, workflow_run_id)
    try:
        api = HfApi(token=hf_token)
        api.whoami()
        info_before = api.repo_info(
            repo_id=SPACE_ID,
            repo_type=REPO_TYPE,
            files_metadata=True,
        )
        if bool(getattr(info_before, "private", False)):
            api.update_repo_settings(
                repo_id=SPACE_ID,
                repo_type=REPO_TYPE,
                private=False,
            )
        parent_revision = str(getattr(info_before, "sha", "") or "").lower()
        if SHA40.fullmatch(parent_revision) is None:
            raise RuntimeError("current destination revision unavailable")
        before_runtime = runtime_state(api)
        if before_runtime["hardwareCurrent"] != EXPECTED_HARDWARE:
            raise RuntimeError(f"unexpected paid/current hardware: {before_runtime}")
        if before_runtime["hardwareRequested"] != EXPECTED_HARDWARE:
            raise RuntimeError(f"unexpected requested hardware: {before_runtime}")

        desired_paths = {
            path.relative_to(stage).as_posix(): path for path in source_files(stage)
        }
        remote_paths = set(
            api.list_repo_files(
                repo_id=SPACE_ID,
                repo_type=REPO_TYPE,
                revision=parent_revision,
            )
        )
        operations: list[CommitOperationAdd | CommitOperationDelete] = [
            CommitOperationDelete(path_in_repo=relative, is_folder=False)
            for relative in sorted(remote_paths - set(desired_paths))
        ]
        operations.extend(
            CommitOperationAdd(path_in_repo=relative, path_or_fileobj=path)
            for relative, path in sorted(desired_paths.items())
        )
        commit = api.create_commit(
            repo_id=SPACE_ID,
            repo_type=REPO_TYPE,
            operations=operations,
            commit_message=f"publish protected source {source_revision[:12]}",
            commit_description=(
                f"Source: {repository}@{source_revision}\n"
                f"GitHub Actions run: {workflow_run_id}\n"
                "Authority: protected-main canonical publisher"
            ),
            parent_commit=parent_revision,
        )
        target_revision = str(
            getattr(commit, "oid", "")
            or getattr(commit, "commit_id", "")
            or ""
        ).lower()
        if SHA40.fullmatch(target_revision) is None:
            raise RuntimeError(f"publisher did not return immutable revision: {commit!r}")

        provider = wait_for_runtime(api, target_revision)
        immutable_files = verify_immutable_tree(api, stage, target_revision)
        binding = json.loads(
            immutable_bytes(target_revision, "szl-source-binding.json").decode("utf-8")
        )
        if binding.get("source", {}).get("revision") != source_revision:
            raise RuntimeError("immutable source binding lost GitHub revision")
        if binding.get("workflow", {}).get("runId") != workflow_run_id:
            raise RuntimeError("immutable source binding lost workflow run")
        if binding.get("managedFiles") != source_managed:
            raise RuntimeError("immutable source binding managed-file set drifted")

        live = verify_live(target_revision)
        receipt = {
            "schema": "szl.constellation-deployment/v1",
            "state": "DEPLOYED_LIVE_VERIFIED",
            "source": {
                "repository": repository,
                "revision": source_revision,
                "protectedMainAtPublish": protected_main,
            },
            "workflow": {
                "runId": workflow_run_id,
                "runAttempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
            },
            "destination": {
                "repoId": SPACE_ID,
                "parentRevision": parent_revision,
                "revision": target_revision,
                "provider": provider,
                "visibility": "public",
            },
            "localVerification": local_verification,
            "immutableFiles": immutable_files,
            "immutableTreeSha256": tree_digest(immutable_files),
            "live": live,
            "limitations": [
                "The source-binding receipt is content-addressed but not cryptographically signed.",
                "Live reachability and source equality do not certify model quality or operational outcomes.",
                "Synthetic public scenarios remain advisory and have no effector authority.",
            ],
        }
        receipt_path = ROOT / "artifacts" / "constellation-deployment-receipt.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(receipt, sort_keys=True), flush=True)
        return receipt
    finally:
        holder.cleanup()


def main() -> int:
    publish()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
