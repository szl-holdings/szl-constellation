"""The packaged publisher declaration is checked locally, not treated as a signature."""

import hashlib
import json
import os

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import pytest

import app as constellation


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _tree_digest(managed):
    return _digest(json.dumps(managed, sort_keys=True, separators=(",", ":")).encode())


def _package(root, space_id=constellation.DEFAULT_SPACE_ID):
    contents = {
        "app.py": b"synthetic app bytes",
        "README.md": b"synthetic card",
        "estates.json": b"{}",
        "verticals.json": b"{}",
        "holo/demo.html": b"<html></html>",
    }
    managed = {}
    for relative, data in contents.items():
        path = root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        managed[relative] = {"bytes": len(data), "sha256": _digest(data)}
    production = space_id == constellation.DEFAULT_SPACE_ID
    manifest = {
        "schema": "szl.github-to-huggingface-source/v1",
        "state": "SOURCE_BOUND_PUBLICATION",
        "source": {
            "repository": "szl-holdings/szl-constellation",
            "revision": "a" * 40,
            "path": "space",
            "relation": "protected-main-canonical-publisher",
        },
        "destination": {
            "target": "production" if production else "staging",
            "repoId": space_id,
            "repoType": "space",
            "visibility": "public" if production else "private",
            "hardware": "cpu-basic",
        },
        "workflow": {"runId": "12345", "runAttempt": "1"},
        "managedFiles": managed,
        "managedTreeSha256": _tree_digest(managed),
    }
    _write_manifest(root, manifest)
    return manifest


def _write_manifest(root, manifest):
    (root / constellation.SOURCE_BINDING_NAME).write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )


@pytest.mark.parametrize(
    "space_id",
    [constellation.DEFAULT_SPACE_ID, "SZLHOLDINGS/szl-constellation-staging"],
)
def test_valid_packaged_manifest_verifies_exact_bytes_for_both_targets(tmp_path, space_id):
    _package(tmp_path, space_id)
    binding = constellation.publisher_source_binding(tmp_path, space_id)
    assert binding["state"] == "LOCAL_BYTES_VERIFIED"
    assert binding["space_id"] == space_id
    assert binding["source_revision"] == "a" * 40
    assert binding["managed_file_count"] == 5
    assert binding["publisher_run_id"] == "12345"
    assert binding["source_authority"] == "PUBLISHER_DECLARED"
    assert binding["github_attestation"] == "NOT_PERFORMED_AT_RUNTIME"


def test_missing_and_malformed_manifest_cannot_claim_source(tmp_path):
    missing = constellation.publisher_source_binding(tmp_path)
    assert missing["state"] == "UNAVAILABLE"
    assert missing["source_revision"] == "UNAVAILABLE"

    (tmp_path / constellation.SOURCE_BINDING_NAME).write_bytes(b'{"schema":NaN}')
    malformed = constellation.publisher_source_binding(tmp_path)
    assert malformed["state"] == "UNAVAILABLE"
    assert malformed["source_revision"] == "UNAVAILABLE"


def test_duplicate_json_key_and_oversized_manifest_are_rejected(tmp_path):
    path = tmp_path / constellation.SOURCE_BINDING_NAME
    path.write_bytes(b'{"schema":"one","schema":"two"}')
    assert constellation.publisher_source_binding(tmp_path)["state"] == "UNAVAILABLE"

    path.write_bytes(b"x" * (constellation.MAX_SOURCE_BINDING_BYTES + 1))
    assert constellation.publisher_source_binding(tmp_path)["state"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.update(schema="unknown"),
        lambda m: m["source"].update(repository="other/repo"),
        lambda m: m["source"].update(revision="A" * 40),
        lambda m: m["source"].update(path="other"),
        lambda m: m["destination"].update(repoId="SZLHOLDINGS/other"),
        lambda m: m["destination"].update(visibility="private"),
        lambda m: m["workflow"].update(runId="not-a-run"),
        lambda m: m.update(managedTreeSha256="0" * 64),
        lambda m: m["managedFiles"]["app.py"].update(sha256="0" * 64),
    ],
)
def test_manifest_claim_or_tree_mismatch_fails_closed(tmp_path, change):
    manifest = _package(tmp_path)
    change(manifest)
    _write_manifest(tmp_path, manifest)
    result = constellation.publisher_source_binding(tmp_path)
    assert result["state"] == "UNAVAILABLE"
    assert result["source_revision"] == "UNAVAILABLE"


def test_changed_packaged_file_fails_closed(tmp_path):
    _package(tmp_path)
    (tmp_path / "holo" / "demo.html").write_bytes(b"changed")
    assert constellation.publisher_source_binding(tmp_path)["state"] == "UNAVAILABLE"


def test_relative_paths_cannot_escape_the_packaged_tree(tmp_path):
    manifest = _package(tmp_path)
    manifest["managedFiles"]["../outside.txt"] = {"bytes": 0, "sha256": _digest(b"")}
    _write_manifest(tmp_path, manifest)
    assert constellation.publisher_source_binding(tmp_path)["state"] == "UNAVAILABLE"


def test_in_tree_symlink_cannot_substitute_for_a_managed_file(tmp_path):
    _package(tmp_path)
    asset = tmp_path / "holo" / "demo.html"
    alias = tmp_path / "holo" / "alias.html"
    alias.write_bytes(asset.read_bytes())
    asset.unlink()
    try:
        asset.symlink_to(alias)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {type(error).__name__}")
    assert constellation.publisher_source_binding(tmp_path)["state"] == "UNAVAILABLE"


def test_private_staging_binding_cannot_be_mislabeled_public(tmp_path):
    staging = "SZLHOLDINGS/szl-constellation-staging"
    manifest = _package(tmp_path, staging)
    manifest["destination"]["visibility"] = "public"
    _write_manifest(tmp_path, manifest)
    assert constellation.publisher_source_binding(tmp_path, staging)["state"] == "UNAVAILABLE"
