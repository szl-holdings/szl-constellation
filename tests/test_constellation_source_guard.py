#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline adversarial tests for Constellation's advisory source guard."""
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import constellation_source_guard as guard

SRC = "a" * 40
HUB_REV = "b" * 40


def fixture(target="production"):
    spec = guard.TARGETS[target]
    files = {"app.py": {"bytes": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}}
    binding = {
        "schema": "szl.github-to-huggingface-source/v1",
        "state": "SOURCE_BOUND_PUBLICATION",
        "source": {
            "repository": "szl-holdings/szl-constellation",
            "revision": SRC, "path": "space",
            "relation": "protected-main-canonical-publisher",
        },
        "destination": {
            "repoId": spec.space_id, "repoType": "space",
            "target": target, "visibility": spec.visibility,
        },
        "managedFiles": files,
        "managedTreeSha256": guard.managed_digest(files),
    }
    meta = {"id": spec.space_id, "private": spec.private, "sha": HUB_REV}
    return meta, binding


class GuardTests(unittest.TestCase):
    def test_offline_policy_not_runtime(self):
        self.assertEqual(guard.policy_check()["status"], "PASS_OFFLINE")
        self.assertFalse(guard.policy_check()["release_admitted"])

    def test_matching_public_snapshot_unsigned(self):
        meta, binding = fixture()
        verdict = guard.judge("production", meta, binding, SRC)
        self.assertEqual(verdict["status"], "PASS_OBSERVED_UNSIGNED")
        self.assertFalse(verdict["signed_receipt_verified"])

    def test_public_staging_is_drift_without_token(self):
        meta, _ = fixture("staging")
        meta["private"] = False
        result = guard.judge("staging", meta, None, "")
        self.assertEqual(result["reason"], "VISIBILITY_CONTRADICTS_SOURCE")
        self.assertEqual(result["status"], "DRIFT")

    def test_private_staging_without_token_is_unknown(self):
        meta, binding = fixture("staging")
        with patch.object(guard, "fetch_json", return_value=(200, meta)):
            res = guard.inspect_live("staging", SRC, None)
        self.assertEqual(res["status"], "UNKNOWN")
        self.assertEqual(res["reason"], "PRIVATE_READ_TOKEN_UNAVAILABLE")

    def test_anonymous_private_staging_401_unknown(self):
        with patch.object(guard, "fetch_json", return_value=(401, None)):
            res = guard.inspect_live("staging", SRC, None)
        self.assertEqual(res["status"], "UNKNOWN")

    def test_wrong_hub_id_unknown_no_foreign_data(self):
        meta, binding = fixture()
        meta["id"] = "other/space"
        self.assertEqual(guard.judge("production", meta, binding, SRC)["status"], "UNKNOWN")

    def test_missing_visibility_unknown(self):
        meta, binding = fixture()
        meta.pop("private")
        self.assertEqual(guard.judge("production", meta, binding, SRC)["status"], "UNKNOWN")

    def test_different_github_revision_drift(self):
        meta, binding = fixture()
        self.assertEqual(guard.judge("production", meta, binding, "c"*40)["reason"],
                         "GITHUB_HUB_SOURCE_REVISION_MISMATCH")

    def test_wrong_destination_drift(self):
        meta, binding = fixture()
        binding["destination"]["repoId"] = "SZLHOLDINGS/wrong"
        self.assertEqual(guard.judge("production", meta, binding, SRC)["status"], "DRIFT")

    def test_modified_manifest_digest_drift(self):
        meta, binding = fixture()
        binding["managedFiles"]["app.py"]["bytes"] = 4
        self.assertEqual(guard.judge("production", meta, binding, SRC)["reason"],
                         "SOURCE_BINDING_TREE_DIGEST_MISMATCH")

    def test_path_escape_and_oversized_metadata_denied(self):
        for unsafe in ("../secrets", "/etc/passwd", "a//b", "a?token=x",
                       "a\\\\b", "app.py#fragment"):
            self.assertFalse(guard.admitted_path(unsafe), unsafe)
        meta, binding = fixture()
        binding["managedFiles"] = {
            "../secrets": {"sha256": hashlib.sha256(b"a").hexdigest(), "bytes": 1}
        }
        binding["managedTreeSha256"] = guard.managed_digest(binding["managedFiles"])
        self.assertEqual(guard.judge("production", meta, binding, SRC)["reason"],
                         "SOURCE_BINDING_FILE_ENTRY_INVALID")

    def test_actual_managed_bytes_mismatch_drift(self):
        meta, binding = fixture()
        out = guard.judge("production", meta, binding, SRC, mismatches=1)
        self.assertEqual(out["reason"], "MANAGED_FILE_BYTE_MISMATCH")

    def test_provider_reads_incomplete_unknown_not_pass(self):
        meta, binding = fixture()
        out = guard.judge("production", meta, binding, SRC, missing_or_denied=1)
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertFalse(out["release_admitted"])

    def test_cross_origin_token_redirect_rejected(self):
        handler = guard.BoundTokenRedirect()
        request = urllib.request.Request(
            "https://huggingface.co/spaces/SZLHOLDINGS/test/resolve/main/app.py",
            headers={"Authorization": "Bearer TEST_FAKE_VALUE"})
        with self.assertRaises(RuntimeError):
            handler.redirect_request(
                request, None, 302, "Found", {},
                "https://example.org/redirected")

    def test_non_hub_fetch_fails_before_network(self):
        with self.assertRaises(ValueError):
            guard.fetch_bytes("https://example.org/api", token="fake")

    def test_private_staging_public_detection_live_no_binding_fetch(self):
        meta, binding = fixture("staging")
        meta["private"] = False
        with patch.object(guard, "fetch_json", return_value=(200, meta)) as get:
            res = guard.inspect_live("staging", SRC, None)
        self.assertEqual(res["reason"], "VISIBILITY_CONTRADICTS_SOURCE")
        self.assertEqual(get.call_count, 1)

    def test_policy_drift_not_false_pass(self):
        from dataclasses import replace
        tampered = replace(guard.TARGETS["staging"], visibility="public")
        with patch.dict(guard.TARGETS, {"staging": tampered}):
            self.assertEqual(guard.policy_check()["status"], "DRIFT")

    def test_bad_expected_source_unknown_not_success(self):
        meta, binding = fixture()
        self.assertEqual(guard.judge("production", meta, binding, "")["status"],
                         "UNKNOWN")


    def test_staging_historical_source_not_false_drift(self):
        meta, binding = fixture("staging")
        result = guard.judge("staging", meta, binding, "c" * 40)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["reason"], "STAGING_SOURCE_NOT_CURRENT")

    def test_live_foreign_metadata_does_not_request_private_binding(self):
        meta, binding = fixture("staging")
        meta["id"] = "not-ours/staging"
        with patch.object(guard, "fetch_json", return_value=(200, meta)) as get:
            result = guard.inspect_live("staging", SRC, "fake-scoped-token")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(get.call_count, 1)


    def test_exact_git_tree_inventory_no_crlf_translation(self):
        import subprocess
        root = Path(__file__).resolve().parents[1]
        head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], timeout=10
        ).decode("ascii").strip()
        state, files = guard.canonical_git_source_inventory(head)
        self.assertEqual(state, "OK")
        self.assertGreater(len(files), 30)
        self.assertIn("app.py", files)
        git_bytes = subprocess.check_output(
            ["git", "-C", str(root), "show", head + ":space/app.py"], timeout=10
        )
        self.assertEqual(files["app.py"]["sha256"],
                         hashlib.sha256(git_bytes).hexdigest())

    def test_git_checkout_revision_mismatch_unknown(self):
        state, files = guard.canonical_git_source_inventory("f" * 40)
        self.assertEqual(state, "SOURCE_CHECKOUT_SHA_MISMATCH")
        self.assertEqual(files, {})

    def test_manifest_omits_source_file_drift_before_hub_fetch(self):
        meta, binding = fixture()
        extra = {"app.py": dict(binding["managedFiles"]["app.py"]),
                 "omitted.py": {"bytes": 3, "sha256": hashlib.sha256(b"def").hexdigest()}}
        with patch.object(guard, "fetch_json", side_effect=[
            (200, meta), (200, binding),
        ]), patch.object(guard, "canonical_git_source_inventory",
                         return_value=("OK", extra)), patch.object(
                             guard, "fetch_bytes") as get:
            result = guard.inspect_live("production", SRC, None)
        self.assertEqual(result["status"], "DRIFT")
        self.assertEqual(result["reason"], "GITHUB_HUB_MANAGED_FILE_SET_OR_BYTES_MISMATCH")
        get.assert_not_called()

    def test_source_tree_unavailable_never_becomes_a_pass(self):
        meta, binding = fixture()
        with patch.object(guard, "fetch_json", side_effect=[
            (200, meta), (200, binding),
        ]), patch.object(guard, "canonical_git_source_inventory",
                         return_value=("GITHUB_SOURCE_READ_UNAVAILABLE", {})):
            result = guard.inspect_live("production", SRC, None)
        self.assertEqual(result["status"], "UNKNOWN")


    def test_hub_added_file_is_drift_even_if_binding_unchanged(self):
        entries = [{"path": "app.py", "type": "file"},
                   {"path": guard.BINDING, "type": "file"},
                   {"path": "unmanaged.py", "type": "file"}]
        with patch.object(guard, "fetch_bytes",
                          return_value=(200, json.dumps(entries).encode("utf-8"))):
            result = guard.inspect_hub_tree(
                "SZLHOLDINGS/szl-constellation", HUB_REV,
                {"app.py", guard.BINDING}, None)
        self.assertEqual(result["status"], "DRIFT")
        self.assertEqual(result["reason"], "HUB_TREE_UNMANAGED_OR_MISSING_FILE")

    def test_hub_incomplete_tree_does_not_pass(self):
        entries = [{"path": "app.py", "type": "file"}]
        with patch.object(guard, "fetch_bytes",
                          return_value=(200, json.dumps(entries).encode("utf-8"))):
            result = guard.inspect_hub_tree(
                "SZLHOLDINGS/szl-constellation", HUB_REV,
                {"app.py", guard.BINDING}, None)
        self.assertEqual(result["status"], "DRIFT")

    def test_hub_tree_unreadable_unknown(self):
        with patch.object(guard, "fetch_bytes", return_value=(403, b"")):
            result = guard.inspect_hub_tree(
                "SZLHOLDINGS/szl-constellation", HUB_REV,
                {"app.py", guard.BINDING}, None)
        self.assertEqual(result["status"], "UNKNOWN")

    def test_full_synthetic_complete_source_and_hub_pass_unsigned(self):
        meta, binding = fixture()
        with patch.object(guard, "fetch_json", side_effect=[
            (200, meta), (200, binding),
        ]), patch.object(guard, "canonical_git_source_inventory",
                         return_value=("OK", binding["managedFiles"])), patch.object(
                             guard, "inspect_hub_tree",
                             return_value=guard.observation("PASS_OFFLINE", "TREE_EQUAL")
                         ), patch.object(guard, "fetch_bytes",
                                         return_value=(200, b"abc")):
            result = guard.inspect_live("production", SRC, None)
        self.assertEqual(result["status"], "PASS_OBSERVED_UNSIGNED")
        self.assertEqual(result["compared_files"], 1)
        self.assertFalse(result["release_admitted"])

    def test_no_signature_claim_even_on_pass(self):
        meta, binding = fixture()
        verdict = guard.judge("production", meta, binding, SRC)
        self.assertEqual(verdict["release_admitted"], False)
        self.assertEqual(verdict["signed_receipt_verified"], False)


if __name__ == "__main__":
    unittest.main()
