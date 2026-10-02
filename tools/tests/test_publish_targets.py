# SPDX-License-Identifier: Apache-2.0
"""Offline contracts for the two publisher targets and their Hub write locks.

No test opens a network connection or constructs a real Hub client: the Hub is
a recording fake and every HTTP read is served from that fake.
"""

from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

import constellation_targets as targets
import publish_constellation as publisher
import verify_constellation as verifier

SOURCE = "a" * 40
PARENT = "b" * 40
CREATED = "c" * 40
TOKEN = "hf_" + "x" * 30


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("offline publisher test attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


@pytest.fixture(autouse=True)
def bounded_polling(monkeypatch):
    """A fake Hub converges at once; any real wait is a contract failure."""

    naps = []

    def nap(seconds):
        naps.append(seconds)
        if len(naps) > 3:
            pytest.fail("publisher kept polling a fake Hub that had already settled")

    monkeypatch.setattr(publisher.time, "sleep", nap)


class FakeHub:
    """Records every call; converges immediately unless told otherwise."""

    def __init__(self, target, *, private, stage_after_commit="RUNNING"):
        self.target = target
        self.private = private
        self.head = PARENT
        self.stage = "RUNNING"
        self.stage_after_commit = stage_after_commit
        self.domain_stage = "READY"
        self.files = {"README.md": b"old", "stale.txt": b"stale"}
        self.calls = []
        self.reads = []

    def whoami(self):
        self.calls.append(("whoami",))
        return {"name": "publisher"}

    def repo_info(self, repo_id, repo_type, files_metadata=False):
        self.calls.append(("repo_info", repo_id))
        return SimpleNamespace(sha=self.head, private=self.private)

    def get_space_runtime(self, repo_id):
        self.calls.append(("get_space_runtime", repo_id))
        sleeping = self.stage in {"SLEEPING", "PAUSED"}
        return SimpleNamespace(
            stage=self.stage,
            raw={
                "sha": self.head,
                "hardware": {
                    "current": None if sleeping else "cpu-basic",
                    "requested": "cpu-basic",
                },
                "replicas": {"current": 1, "requested": 1},
                "domains": [{"domain": self.target.live_host, "stage": self.domain_stage}],
            },
        )

    def list_repo_files(self, repo_id, repo_type, revision):
        self.calls.append(("list_repo_files", repo_id, revision))
        return list(self.files)

    def create_commit(self, **kwargs):
        self.calls.append(("create_commit", kwargs["repo_id"], kwargs["parent_commit"]))
        for operation in kwargs["operations"]:
            if isinstance(operation, publisher.CommitOperationDelete):
                self.files.pop(operation.path_in_repo, None)
            else:
                self.files[operation.path_in_repo] = Path(operation.path_or_fileobj).read_bytes()
        self.head = CREATED
        self.stage = self.stage_after_commit
        return SimpleNamespace(oid=CREATED)

    def update_repo_settings(self, **kwargs):
        self.calls.append(("update_repo_settings", kwargs))

    def restart_space(self, **kwargs):
        self.calls.append(("restart_space", kwargs))

    def serve(self, url, *, timeout=30, token=None):
        self.reads.append((url, token))
        prefix = f"https://huggingface.co/spaces/{self.target.space_id}/resolve/{CREATED}/"
        assert url.startswith(prefix), url
        relative = url[len(prefix):].split("?", 1)[0]
        return 200, "application/octet-stream", self.files[relative]


@pytest.fixture
def run_publish(monkeypatch, tmp_path):
    def run(name, *, private, stage_after_commit="RUNNING"):
        target = targets.TARGETS[name]
        hub = FakeHub(target, private=private, stage_after_commit=stage_after_commit)
        probes = {}
        monkeypatch.setenv("CONSTELLATION_TARGET", name)
        monkeypatch.setenv("HF_TOKEN", TOKEN)
        monkeypatch.setenv("GITHUB_TOKEN", "github-offline")
        monkeypatch.setenv("GITHUB_SHA", SOURCE)
        monkeypatch.setenv("GITHUB_RUN_ID", "4242")
        monkeypatch.setenv("GITHUB_REPOSITORY", "szl-holdings/szl-constellation")
        monkeypatch.setattr(publisher, "ROOT", tmp_path)
        monkeypatch.setattr(publisher, "HfApi", lambda token: hub)
        monkeypatch.setattr(publisher, "current_protected_main", lambda repository, token: SOURCE)
        monkeypatch.setattr(publisher, "request_bytes", hub.serve)
        monkeypatch.setattr(
            publisher, "verify_live", lambda revision: probes.setdefault("public", revision)
        )
        monkeypatch.setattr(
            publisher,
            "verify_private_live",
            lambda target, token, app_sha256: probes.setdefault(
                "private", (target.name, token == TOKEN, app_sha256)
            ),
        )
        receipt = publisher.publish()
        return hub, probes, receipt

    return run


def test_absent_or_empty_target_means_production():
    assert targets.resolve_target({}).name == targets.PRODUCTION
    assert targets.resolve_target({"CONSTELLATION_TARGET": " "}).name == targets.PRODUCTION
    assert targets.resolve_target({"CONSTELLATION_TARGET": "staging"}).name == targets.STAGING


def test_unknown_target_fails_closed():
    with pytest.raises(RuntimeError, match="unknown CONSTELLATION_TARGET"):
        targets.resolve_target({"CONSTELLATION_TARGET": "SZLHOLDINGS/other"})


def test_targets_are_the_two_fixed_spaces_with_canonical_locks():
    production = targets.TARGETS[targets.PRODUCTION]
    staging = targets.TARGETS[targets.STAGING]
    assert (production.space_id, production.visibility) == ("SZLHOLDINGS/szl-constellation", "public")
    assert (staging.space_id, staging.visibility) == ("SZLHOLDINGS/szl-constellation-staging", "private")
    assert production.lock_group == "hf-write/space/SZLHOLDINGS/szl-constellation"
    assert staging.lock_group == "hf-write/space/SZLHOLDINGS/szl-constellation-staging"
    assert staging.oidc_resource == "spaces/SZLHOLDINGS/szl-constellation-staging"
    assert publisher.SPACE_ID == production.space_id
    assert publisher.LIVE_BASE == "https://szlholdings-szl-constellation.hf.space"


def test_production_publish_is_unchanged(run_publish):
    hub, probes, receipt = run_publish(targets.PRODUCTION, private=False)
    commits = [call for call in hub.calls if call[0] == "create_commit"]
    assert commits == [("create_commit", "SZLHOLDINGS/szl-constellation", PARENT)]
    assert not [call for call in hub.calls if call[0] in {"update_repo_settings", "restart_space"}]
    assert "stale.txt" not in hub.files
    assert probes == {"public": CREATED}
    assert all(token is None for _url, token in hub.reads), "public readback must be anonymous"
    assert receipt["state"] == "DEPLOYED_LIVE_VERIFIED"
    assert receipt["target"] == "production"
    assert receipt["destination"]["repoId"] == "SZLHOLDINGS/szl-constellation"
    assert receipt["destination"]["visibility"] == "public"
    assert receipt["destination"]["lock"] == "hf-write/space/SZLHOLDINGS/szl-constellation"
    binding = json.loads(hub.files["szl-source-binding.json"])
    assert binding["destination"]["repoId"] == "SZLHOLDINGS/szl-constellation"
    assert binding["source"]["revision"] == SOURCE


def test_staging_publish_stays_private_and_reads_back_with_the_credential(run_publish):
    hub, probes, receipt = run_publish(targets.STAGING, private=True)
    commits = [call for call in hub.calls if call[0] == "create_commit"]
    assert commits == [("create_commit", "SZLHOLDINGS/szl-constellation-staging", PARENT)]
    assert not [call for call in hub.calls if call[0] == "update_repo_settings"]
    assert all(
        call[1] == "SZLHOLDINGS/szl-constellation-staging"
        for call in hub.calls
        if call[0] in {"repo_info", "get_space_runtime", "list_repo_files"}
    )
    assert hub.reads and all(token == TOKEN for _url, token in hub.reads)
    app_sha256 = hashlib.sha256(hub.files["app.py"]).hexdigest()
    assert probes == {"private": ("staging", True, app_sha256)}
    assert receipt["state"] == "DEPLOYED_LIVE_VERIFIED"
    assert receipt["target"] == "staging"
    assert receipt["destination"]["visibility"] == "private"
    assert receipt["destination"]["lock"] == "hf-write/space/SZLHOLDINGS/szl-constellation-staging"
    binding = json.loads(hub.files["szl-source-binding.json"])
    assert binding["destination"]["repoId"] == "SZLHOLDINGS/szl-constellation-staging"
    assert binding["destination"]["visibility"] == "private"
    assert TOKEN not in json.dumps(receipt)


VISIBILITY_MISMATCH = [
    pytest.param(targets.STAGING, False, "must be private", id="public-staging"),
    pytest.param(targets.PRODUCTION, True, "must be public", id="private-production"),
]


@pytest.mark.parametrize("name,private,message", VISIBILITY_MISMATCH)
def test_visibility_mismatch_is_refused_before_any_write(run_publish, name, private, message):
    with pytest.raises(RuntimeError, match=message):
        run_publish(name, private=private)


@pytest.mark.parametrize("name,private,message", VISIBILITY_MISMATCH)
def test_visibility_mismatch_never_triggers_a_settings_write(
    monkeypatch, tmp_path, name, private, message
):
    # Visibility is an owner setting: the publisher only reads it, for both
    # targets, and stops after the first repo_info.
    target = targets.TARGETS[name]
    hub = FakeHub(target, private=private)
    monkeypatch.setenv("CONSTELLATION_TARGET", name)
    for variable, value in {
        "HF_TOKEN": TOKEN,
        "GITHUB_TOKEN": "github-offline",
        "GITHUB_SHA": SOURCE,
        "GITHUB_RUN_ID": "1",
        "GITHUB_REPOSITORY": "szl-holdings/szl-constellation",
    }.items():
        monkeypatch.setenv(variable, value)
    monkeypatch.setattr(publisher, "ROOT", tmp_path)
    monkeypatch.setattr(publisher, "HfApi", lambda token: hub)
    monkeypatch.setattr(publisher, "current_protected_main", lambda repository, token: SOURCE)
    with pytest.raises(RuntimeError, match=message):
        publisher.publish()
    assert [call[0] for call in hub.calls] == ["whoami", "repo_info"]


def test_sleeping_private_target_is_terminal_ok_and_never_woken(run_publish):
    hub, probes, receipt = run_publish(targets.STAGING, private=True, stage_after_commit="SLEEPING")
    assert not [call for call in hub.calls if call[0] == "restart_space"]
    assert probes == {}
    assert receipt["state"] == "DEPLOYED_REVISION_VERIFIED_ASLEEP"
    assert receipt["live"]["probe"] == "NOT_ATTEMPTED"
    assert receipt["destination"]["provider"]["terminalWithoutWake"] is True


def test_sleeping_production_target_is_restarted_once():
    target = targets.TARGETS[targets.PRODUCTION]
    hub = FakeHub(target, private=False)
    hub.head = CREATED
    hub.stage = "SLEEPING"
    naps = []

    def nap(seconds):
        naps.append(seconds)
        if len(naps) == 2:
            hub.stage = "RUNNING"

    observed = publisher.wait_for_runtime(hub, CREATED, 60, target, sleep=nap)
    assert observed["stage"] == "RUNNING"
    assert [call[0] for call in hub.calls].count("restart_space") == 1


def test_production_requires_its_public_edge_but_private_staging_does_not():
    production = FakeHub(targets.TARGETS[targets.PRODUCTION], private=False)
    production.head = CREATED
    production.domain_stage = "PENDING"
    with pytest.raises(TimeoutError, match="did not converge"):
        publisher.wait_for_runtime(
            production, CREATED, 0.05, targets.TARGETS[targets.PRODUCTION], sleep=lambda s: None
        )
    staging = FakeHub(targets.TARGETS[targets.STAGING], private=True)
    staging.head = CREATED
    staging.domain_stage = "PENDING"
    observed = publisher.wait_for_runtime(
        staging, CREATED, 0.05, targets.TARGETS[targets.STAGING], sleep=lambda s: None
    )
    assert observed["stage"] == "RUNNING"
    assert observed["domainReady"] is False


@pytest.mark.parametrize("name,private", [("production", True), ("staging", False)])
def test_visibility_drift_during_convergence_fails_closed(name, private):
    target = targets.TARGETS[name]
    hub = FakeHub(target, private=private)
    hub.head = CREATED
    with pytest.raises(RuntimeError, match="visibility drifted"):
        publisher.wait_for_runtime(hub, CREATED, 60, target, sleep=lambda seconds: None)


def test_bearer_header_only_when_a_token_is_given(monkeypatch):
    seen = []

    class Response:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            return b"{}"

    def urlopen(request, timeout):
        seen.append(request.get_header("Authorization"))
        return Response()

    monkeypatch.setattr(publisher.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(
        publisher.urllib.request, "build_opener", lambda handler: SimpleNamespace(open=urlopen)
    )
    publisher.request_bytes("https://huggingface.co/x")
    publisher.request_bytes("https://huggingface.co/x", token=TOKEN)
    assert seen == [None, f"Bearer {TOKEN}"]


def test_private_live_probe_requires_the_published_app_bytes(monkeypatch):
    target = targets.TARGETS[targets.STAGING]
    served = {"ok": True, "app_sha256": "0" * 64}
    calls = []

    def fake_json(url, *, timeout=30, token=None):
        calls.append((url, token))
        return dict(served)

    monkeypatch.setattr(publisher, "request_json", fake_json)
    with pytest.raises(TimeoutError, match="differ from the published app.py"):
        publisher.verify_private_live(target, TOKEN, "1" * 64, attempts=2, sleep=lambda s: None)
    assert calls == [(target.live_base + "/healthz", TOKEN)] * 2
    served["app_sha256"] = "1" * 64
    result = publisher.verify_private_live(target, TOKEN, "1" * 64, attempts=1, sleep=lambda s: None)
    assert result["appBytesMatch"] is True
    assert result["probe"] == "AUTHENTICATED_PRIVATE_HEALTHZ"


def test_workflow_contract_accepts_the_committed_workflow():
    contract = verifier.publisher_credential_contract(verifier.PUBLISH_WORKFLOW)
    assert contract["defaultTarget"] == "production"
    assert set(contract["targets"]) == {"production", "staging"}


@pytest.mark.parametrize(
    "mutation",
    [
        ("    concurrency:\n      group: ${{", "    concurrency:\n      group: constellation-${{"),
        ("permissions:\n", "concurrency:\n  group: constellation-protected-main-publisher\n\npermissions:\n"),
        ("'SZLHOLDINGS/szl-constellation-staging'", "'SZLHOLDINGS/other-space'"),
        ('--target-repo "${TARGET_SPACE}"', "--target-repo SZLHOLDINGS/szl-constellation"),
        ("&& 'staging' || 'production'", "&& 'production' || 'staging'"),
    ],
    ids=["lock-renamed", "workflow-wide-lock", "foreign-space", "fixed-target", "inverted-default"],
)
def test_workflow_contract_rejects_mutations(tmp_path, mutation):
    old, new = mutation
    text = verifier.PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert old in text
    mutated = tmp_path / "publish.yml"
    mutated.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(AssertionError):
        verifier.publisher_credential_contract(mutated)


def test_runtime_identity_allowlist_matches_targets(tmp_path):
    assert verifier.space_identity_contract(verifier.SPACE / "app.py")["valid"] is True
    app = (verifier.SPACE / "app.py").read_text(encoding="utf-8")
    drifted = tmp_path / "app.py"
    drifted.write_text(
        app.replace(
            '"SZLHOLDINGS/szl-constellation-staging": "szlholdings-szl-constellation-staging.hf.space"',
            '"SZLHOLDINGS/other": "szlholdings-other.hf.space"',
        ),
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="KNOWN_SPACE_HOSTS"):
        verifier.space_identity_contract(drifted)
