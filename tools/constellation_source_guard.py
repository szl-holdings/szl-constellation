#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read-only, source-fenced Constellation drift observation; never release authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# Also works with the isolated BETTERWITHAGE Python runner (no implicit script path).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from constellation_targets import PRODUCTION, STAGING, TARGETS

SHA40 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
SOURCE_REPO = "szl-holdings/szl-constellation"
BINDING = "szl-source-binding.json"
HUB = "https://huggingface.co"
MAX_JSON = 1024 * 1024
MAX_FILE = 6 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_MANAGED = 128


def observation(status: str, reason: str, **safe: Any) -> dict[str, Any]:
    return {"schema": "szl.constellation-source-guard/v1", "status": status,
            "reason": reason, "release_admitted": False,
            "signed_receipt_verified": False, **safe}


def policy_check() -> dict[str, Any]:
    prod, stage = TARGETS[PRODUCTION], TARGETS[STAGING]
    valid = (
        prod.space_id == "SZLHOLDINGS/szl-constellation"
        and stage.space_id == "SZLHOLDINGS/szl-constellation-staging"
        and prod.visibility == "public" and stage.visibility == "private"
        and not stage.wake_if_sleeping and prod.space_id != stage.space_id
    )
    return observation("PASS_OFFLINE" if valid else "DRIFT",
                       "DECLARED_TARGET_POLICY_ONLY" if valid else "DECLARED_POLICY_CHANGED")


def admitted_path(path: Any) -> bool:
    if not isinstance(path, str) or not path or len(path) > 240:
        return False
    parts = path.split("/")
    return (
        not path.startswith("/") and len(parts) <= 8 and
        all(p not in ("", ".", "..") for p in parts)
        and not any(c in path for c in ("\\", "?", "#", "\x00", ":"))
        and not path.endswith("/")
    )


def managed_digest(files: dict[str, Any]) -> str:
    payload = json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def judge(target: str, metadata: Any, binding: Any,
          expected_source: str, mismatches: int = 0,
          missing_or_denied: int = 0) -> dict[str, Any]:
    spec = TARGETS[target]
    if not isinstance(metadata, dict) or metadata.get("id") != spec.space_id:
        return observation("UNKNOWN", "HUB_IDENTITY_UNAVAILABLE")
    observed_private = metadata.get("private")
    if type(observed_private) is not bool:
        return observation("UNKNOWN", "VISIBILITY_UNKNOWN")
    if observed_private != spec.private:
        return observation("DRIFT", "VISIBILITY_CONTRADICTS_SOURCE",
                           target=target, expected_visibility=spec.visibility,
                           observed_visibility="private" if observed_private else "public")
    if not isinstance(expected_source, str) or not SHA40.fullmatch(expected_source):
        return observation("UNKNOWN", "EXPECTED_SOURCE_SHA_UNAVAILABLE")
    if not isinstance(binding, dict):
        return observation("UNKNOWN", "SOURCE_BINDING_UNAVAILABLE", target=target)
    source, dest = binding.get("source"), binding.get("destination")
    if not isinstance(source, dict) or not isinstance(dest, dict):
        return observation("DRIFT", "SOURCE_BINDING_SCHEMA_INVALID", target=target)
    if (binding.get("schema") != "szl.github-to-huggingface-source/v1"
        or binding.get("state") != "SOURCE_BOUND_PUBLICATION"
        or source.get("repository") != SOURCE_REPO
        or source.get("path") != "space"
        or source.get("relation") != "protected-main-canonical-publisher"
        or dest.get("repoId") != spec.space_id
        or dest.get("target") != target
        or dest.get("visibility") != spec.visibility
        or dest.get("repoType") != "space"):
        return observation("DRIFT", "SOURCE_BINDING_IDENTITY_MISMATCH", target=target)
    revision = source.get("revision")
    if not isinstance(revision, str) or not SHA40.fullmatch(revision):
        return observation("DRIFT", "SOURCE_BINDING_REVISION_MALFORMED", target=target)
    if revision != expected_source:
        # A private rehearsal is not required to track every later main commit.
        status = "UNKNOWN" if target == STAGING else "DRIFT"
        reason = ("STAGING_SOURCE_NOT_CURRENT" if target == STAGING
                  else "GITHUB_HUB_SOURCE_REVISION_MISMATCH")
        return observation(status, reason, target=target,
                           expected_main_sha=expected_source, bound_source_sha=revision)
    files = binding.get("managedFiles")
    if not isinstance(files, dict) or not (1 <= len(files) <= MAX_MANAGED):
        return observation("DRIFT", "SOURCE_BINDING_FILE_SET_INVALID", target=target)
    for path, detail in files.items():
        if (not admitted_path(path) or path == BINDING or not isinstance(detail, dict)
            or not SHA256.fullmatch(str(detail.get("sha256") or ""))
            or type(detail.get("bytes")) is not int
            or not (0 <= detail["bytes"] <= MAX_FILE)):
            return observation("DRIFT", "SOURCE_BINDING_FILE_ENTRY_INVALID", target=target)
    if managed_digest(files) != binding.get("managedTreeSha256"):
        return observation("DRIFT", "SOURCE_BINDING_TREE_DIGEST_MISMATCH", target=target)
    if mismatches:
        return observation("DRIFT", "MANAGED_FILE_BYTE_MISMATCH", target=target,
                           compared_files=len(files), mismatches=mismatches)
    if missing_or_denied:
        return observation("UNKNOWN", "MANAGED_FILE_READ_INCOMPLETE", target=target,
                           compared_files=len(files), unavailable=missing_or_denied)
    return observation("PASS_OBSERVED_UNSIGNED", "PUBLICATION_BYTES_OBSERVED_NOT_SIGNED",
                       target=target, source_revision=revision, compared_files=len(files))


class BoundTokenRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward an HF read token to an external host or non-HTTPS URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = urllib.parse.urlsplit(newurl)
        if new.scheme != "https" or new.hostname != "huggingface.co" or new.port not in (None, 443):
            raise RuntimeError("CROSS_ORIGIN_REDIRECT_DENIED")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_bytes(url: str, *, token: str | None = None,
                cap: int = MAX_JSON) -> tuple[int, bytes]:
    if not url.startswith(HUB + "/"):
        raise ValueError("HUB_ORIGIN_REQUIRED")
    headers = {"Accept": "application/json", "User-Agent": "szl-constellation-guard/1"}
    opener = urllib.request.urlopen
    if token:
        headers["Authorization"] = "Bearer " + token
        opener = urllib.request.build_opener(BoundTokenRedirect()).open
    req = urllib.request.Request(url, headers=headers)
    try:
        with opener(req, timeout=12) as response:
            data = response.read(cap + 1)
            if len(data) > cap:
                raise ValueError("OBSERVATION_TOO_LARGE")
            return int(response.status), data
    except urllib.error.HTTPError as error:
        return int(error.code), b""


def fetch_json(url: str, token: str | None = None) -> tuple[int, Any]:
    status, data = fetch_bytes(url, token=token)
    if status != 200:
        return status, None
    try:
        value = json.loads(data)
        return status, value if isinstance(value, dict) else None
    except (ValueError, UnicodeDecodeError):
        return 200, None



def canonical_git_source_inventory(source_sha: str) -> tuple[str, dict[str, dict[str, Any]]]:
    """Read exact tracked blob bytes, not potentially CRLF-translated checkout files."""
    root = Path(__file__).resolve().parents[1]
    if not SHA40.fullmatch(source_sha) or not (root / ".git").exists():
        return "GITHUB_SOURCE_CHECKOUT_UNAVAILABLE", {}
    def git(*args: str) -> bytes:
        proc = subprocess.run(["git", "-C", str(root), *args],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=20, check=False)
        if proc.returncode:
            raise RuntimeError("GIT_READ_FAILED")
        return proc.stdout
    try:
        if git("rev-parse", "HEAD").decode("ascii").strip() != source_sha:
            return "SOURCE_CHECKOUT_SHA_MISMATCH", {}
        names = git("ls-tree", "-r", "--name-only", "-z", source_sha, "space")
        paths = [entry.decode("utf-8") for entry in names.split(bytes([0])) if entry]
        if not (1 <= len(paths) <= MAX_MANAGED):
            return "GITHUB_MANAGED_PATH_COUNT_UNAVAILABLE", {}
        inventory: dict[str, dict[str, Any]] = {}
        total = 0
        for full_path in paths:
            if not full_path.startswith("space/"):
                return "GITHUB_PATH_OUTSIDE_SPACE", {}
            rel = full_path[len("space/"):]
            if "__pycache__" in rel.split("/") or rel.endswith((".pyc", ".pyo")):
                continue
            if not admitted_path(rel):
                return "GITHUB_MANAGED_PATH_INVALID", {}
            data = git("show", f"{source_sha}:{full_path}")
            total += len(data)
            if len(data) > MAX_FILE or total > MAX_TOTAL:
                return "GITHUB_MANAGED_BYTE_BUDGET_EXCEEDED", {}
            inventory[rel] = {"bytes": len(data),
                              "sha256": hashlib.sha256(data).hexdigest()}
        if not inventory:
            return "GITHUB_MANAGED_PATH_COUNT_UNAVAILABLE", {}
        return "OK", inventory
    except (OSError, RuntimeError, UnicodeError, subprocess.SubprocessError):
        return "GITHUB_SOURCE_READ_UNAVAILABLE", {}



def inspect_hub_tree(slug: str, hub_sha: str, expected: set[str],
                     token: str | None) -> dict[str, Any]:
    """Catch an extra Hub-side file outside the canonical publisher manifest."""
    url = f"{HUB}/api/spaces/{slug}/tree/{hub_sha}?recursive=true"
    try:
        status, data = fetch_bytes(url, token=token, cap=MAX_JSON)
        if status != 200:
            return observation("UNKNOWN", "HUB_TREE_UNAVAILABLE", http=status)
        entries = json.loads(data)
        if not isinstance(entries, list) or len(entries) >= 100:
            return observation("UNKNOWN", "HUB_TREE_PAGINATION_OR_SCHEMA_UNVERIFIED")
        files = [item["path"] for item in entries
                 if isinstance(item, dict) and item.get("type") == "file"
                 and isinstance(item.get("path"), str)]
        if (not files or len(set(files)) != len(files)
                or not all(admitted_path(p) for p in files)):
            return observation("UNKNOWN", "HUB_TREE_INCOMPLETE_OR_MALFORMED")
        if set(files) != expected:
            return observation("DRIFT", "HUB_TREE_UNMANAGED_OR_MISSING_FILE",
                               expected_files=len(expected), observed_files=len(files))
        return observation("PASS_OFFLINE", "HUB_TREE_IDENTITIES_EQUAL")
    except (OSError, UnicodeError, ValueError, RuntimeError):
        return observation("UNKNOWN", "HUB_TREE_UNAVAILABLE")


def inspect_live(target: str, source_sha: str, token: str | None) -> dict[str, Any]:
    spec = TARGETS[target]
    slug = spec.space_id
    try:
        status, metadata = fetch_json(f"{HUB}/api/spaces/{slug}")
    except (OSError, ValueError, RuntimeError) as exc:
        return observation("UNKNOWN", "HUB_PUBLIC_METADATA_UNAVAILABLE",
                           target=target, error_class=type(exc).__name__)
    if status != 200:
        return observation("UNKNOWN", "HUB_PUBLIC_METADATA_UNAVAILABLE",
                           target=target, http=status)
    # This one check can prove public staging exposure without any credential.
    if (isinstance(metadata, dict) and metadata.get("id") == slug
            and type(metadata.get("private")) is bool
            and metadata["private"] != spec.private):
        return judge(target, metadata, None, source_sha)
    if (not isinstance(metadata, dict) or metadata.get("id") != slug
            or type(metadata.get("private")) is not bool):
        return judge(target, metadata, None, source_sha)
    if target == STAGING and not token:
        return observation("UNKNOWN", "PRIVATE_READ_TOKEN_UNAVAILABLE", target=target)
    hub_sha = metadata.get("sha") if isinstance(metadata, dict) else None
    if not isinstance(hub_sha, str) or not SHA40.fullmatch(hub_sha):
        return observation("UNKNOWN", "HUB_REVISION_UNAVAILABLE", target=target)
    binding_url = f"{HUB}/spaces/{slug}/resolve/{hub_sha}/{BINDING}"
    try:
        status, binding = fetch_json(binding_url, token=token)
    except (OSError, ValueError, RuntimeError) as exc:
        return observation("UNKNOWN", "SOURCE_BINDING_READ_UNAVAILABLE",
                           target=target, error_class=type(exc).__name__)
    if status != 200:
        return observation("UNKNOWN", "SOURCE_BINDING_READ_UNAVAILABLE",
                           target=target, http=status)
    outcome = judge(target, metadata, binding, source_sha)
    if outcome["status"] != "PASS_OBSERVED_UNSIGNED":
        return outcome
    state, github_files = canonical_git_source_inventory(source_sha)
    if state != "OK":
        return observation("UNKNOWN", state, target=target)
    files = binding["managedFiles"]
    if github_files != files:
        return observation("DRIFT", "GITHUB_HUB_MANAGED_FILE_SET_OR_BYTES_MISMATCH",
                           target=target, github_files=len(github_files),
                           bound_files=len(files))
    tree = inspect_hub_tree(slug, hub_sha, set(files) | {BINDING}, token)
    if tree["status"] != "PASS_OFFLINE":
        tree["target"] = target
        return tree
    if sum(f["bytes"] for f in files.values()) > MAX_TOTAL:
        return observation("UNKNOWN", "MANAGED_BYTE_BUDGET_EXCEEDED", target=target)
    mismatches = unavailable = 0
    for path, meta in sorted(files.items()):
        url = f"{HUB}/spaces/{slug}/resolve/{hub_sha}/" + urllib.parse.quote(path, safe="/")
        try:
            file_status, content = fetch_bytes(url, token=token, cap=MAX_FILE)
        except (OSError, ValueError, RuntimeError):
            unavailable += 1
            continue
        if file_status in (401, 403, 429, 500, 502, 503, 504):
            unavailable += 1
        elif file_status != 200:
            mismatches += 1
        elif len(content) != meta["bytes"] or hashlib.sha256(content).hexdigest() != meta["sha256"]:
            mismatches += 1
    # Mismatches outrank missing reads, but unknown is never a pass.
    outcome = judge(target, metadata, binding, source_sha, mismatches, unavailable)
    outcome["hub_revision"] = hub_sha
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--target", choices=(PRODUCTION, STAGING), default=PRODUCTION)
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    declaration = policy_check()
    if declaration["status"] == "DRIFT" or args.mode == "offline":
        report = declaration
    else:
        # Never attach a token to a public production read.
        scoped_token = ((os.environ.get("CONSTELLATION_HF_READ_TOKEN") or None)
                        if args.target == STAGING else None)
        report = inspect_live(args.target, args.source_sha.lower(), scoped_token)
    # A successful read proves neither a signature nor authenticated live rendering.
    text = json.dumps(report, sort_keys=True)
    print(text)
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 2 if report["status"] == "DRIFT" else 0


if __name__ == "__main__":
    sys.exit(main())
