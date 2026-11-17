"""Adversarial contract tests for source-fenced public Space runtime stage."""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app
import atlas_runtime as runtime

SHA = "a" * 40
NEW = "b" * 40
ID = "SZLHOLDINGS/anatomy"


def census(sha=SHA):
    return {
        "state": "OBSERVED_PUBLIC_HUB_METADATA",
        "scope": "ANONYMOUS_PUBLIC_HUB_ONLY",
        "private_assets_excluded": True,
        "observed_at": "2026-11-17T13:00:00Z",
        "nodes": [
            {"kind": "space", "id": "space:" + ID,
             "source_revision": sha, "hub_id": ID},
            {"kind": "model", "id": "model:SZLHOLDINGS/szl-khipu",
             "source_revision": SHA}
        ],
    }


def info(*, sha=SHA, private=False, stage="RUNNING", hardware="cpu-basic",
         ident=ID):
    return SimpleNamespace(
        id=ident, private=private, sha=sha,
        runtime=SimpleNamespace(stage=stage, hardware=hardware),
    )


def observe(space="anatomy", state=None, details=None):
    return runtime.observe_public_space_runtime(
        space,
        census_reader=lambda: census() if state is None else state,
        info_reader=lambda fullname: info() if details is None else details,
        clock=lambda: "2026-11-17T13:01:00Z",
    )


def assert_blocked(code, expected, *, status=None):
    with pytest.raises(runtime.RuntimeObservationError) as raised:
        code()
    assert raised.value.reason_code == expected
    if status:
        assert raised.value.http_status == status


def test_running_provider_stage_is_not_health_or_execution():
    result = observe()
    assert result["schema"] == runtime.SCHEMA
    assert result["state"] == "OBSERVED_PROVIDER_RUNTIME_METADATA"
    assert result["space_id"] == ID
    assert result["provider_stage"] == "RUNNING"
    assert result["provider_hardware"] == "cpu-basic"
    assert result["source_binding"] == "PUBLIC_CENSUS_SHA_MATCH"
    assert result["observed_source_revision"] == SHA
    assert result["census_source_revision"] == SHA
    assert result["runtime_readiness"] == "NOT_EVALUATED"
    assert result["model_execution"] == "NOT_EVALUATED"
    assert result["signed_execution_provenance"] == "NOT_EVALUATED"
    assert result["source_byte_attestation"] == "NOT_EVALUATED"
    assert result["production_qualified"] is False
    assert result["execution_authorized"] is False
    unsigned = {k: v for k, v in result.items() if k != "observation_sha256"}
    digest = hashlib.sha256(json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"),
        allow_nan=False, ensure_ascii=False,
    ).encode()).hexdigest()
    assert digest == result["observation_sha256"]


@pytest.mark.parametrize("stage", ["SLEEPING", "BUILDING", "BUILD_ERROR",
                                    "APP_STARTING", "PAUSED"])
def test_nonrunning_stage_is_observed_without_forcing_readiness(stage):
    result = observe(details=info(stage=stage))
    assert result["provider_stage"] == stage
    assert result["runtime_readiness"] == "NOT_EVALUATED"
    assert result["production_qualified"] is False


@pytest.mark.parametrize("name", [
    "", "../secret", "anatomy/../secret", "another-org/anatomy",
    "anatomy?token=x", "anatomy%2fsecret", "anatomy extra", 123, None,
])
def test_foreign_and_invalid_names_denied_before_hub_lookup(name):
    called = []
    def hub(_name):
        called.append(_name)
        raise AssertionError("never query unadmitted URL")
    with pytest.raises(runtime.RuntimeObservationError) as exc:
        runtime.observe_public_space_runtime(
            name, census_reader=census, info_reader=hub)
    assert exc.value.reason_code == "INVALID_PUBLIC_SPACE_NAME"
    assert exc.value.http_status == 400
    assert not called


def test_private_and_unlisted_spaces_look_identical():
    no_node = census()
    no_node["nodes"] = no_node["nodes"][1:]
    assert_blocked(lambda: observe(state=no_node),
                   "SPACE_NOT_IN_PUBLIC_CENSUS", status=404)
    assert_blocked(lambda: observe(details=info(private=True)),
                   "PUBLIC_VISIBILITY_UNVERIFIED", status=404)


def test_mismatched_identical_case_or_new_revision_fails_closed():
    assert_blocked(lambda: observe(details=info(ident="OtherOrg/anatomy")),
                   "PUBLIC_VISIBILITY_UNVERIFIED", status=404)
    assert_blocked(lambda: observe(details=info(sha=NEW)),
                   "SPACE_SOURCE_CHANGED_SINCE_CENSUS", status=409)
    assert_blocked(lambda: observe(state=census(sha=NEW)),
                   "SPACE_SOURCE_CHANGED_SINCE_CENSUS", status=409)


def test_unauthorized_and_rate_limited_hub_fail_without_upstream_text():
    for status in (401, 429):
        def read(_name):
            raise RuntimeError("SECRET_TOKEN_UPSTREAM_ERROR_" + str(status))
        with pytest.raises(runtime.RuntimeObservationError) as raised:
            runtime.observe_public_space_runtime(
                "anatomy", census_reader=census, info_reader=read)
        assert raised.value.reason_code == "ANONYMOUS_HUB_SPACE_INFO_UNAVAILABLE"
        denial = runtime.failed_public_observation(raised.value.reason_code)
        assert denial["provider_stage"] is None
        assert "SECRET_TOKEN" not in json.dumps(denial)
        assert denial["production_qualified"] is False


def test_missing_or_unknown_runtime_stage_not_observed():
    assert_blocked(lambda: observe(details=info(stage=None)),
                   "PROVIDER_STAGE_NOT_OBSERVED")
    assert_blocked(lambda: observe(details=info(stage="RUNNING\nPRIVATE")),
                   "PROVIDER_STAGE_NOT_OBSERVED")


def test_untrusted_hardware_string_omitted_not_executed():
    report = observe(details=info(hardware="gpu\nSECRET"))
    assert report["provider_hardware"] is None
    assert "SECRET" not in json.dumps(report)


def test_invalid_census_or_missing_source_rejected():
    assert_blocked(lambda: observe(state={"state": "READY"}),
                   "PUBLIC_CENSUS_UNVERIFIED")
    assert_blocked(lambda: observe(state=census(sha=None)),
                   "PUBLIC_SOURCE_REVISION_UNVERIFIED")


def test_anonymous_hub_read_never_inherits_saved_token():
    calls = []
    class FakeApi:
        def __init__(self, token):
            calls.append(("ctor", token))
        def space_info(self, name, *, timeout, token):
            calls.append(("info", name, timeout, token))
            return info()
    with patch("huggingface_hub.HfApi", FakeApi):
        assert runtime._read_hub_space(ID).sha == SHA
    assert calls == [("ctor", False), ("info", ID, 10, False)]


def test_route_returns_fresh_anonymous_public_observation():
    value = observe()
    with patch.object(app, "observe_public_space_runtime", return_value=value):
        client = TestClient(app.app)
        response = client.get("/api/atlas/space-runtime/anatomy")
    assert response.status_code == 200
    assert response.json() == value
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_route_failure_is_safe_generic_and_not_old_stage():
    client = TestClient(app.app)
    for reason, status in (("SPACE_NOT_IN_PUBLIC_CENSUS", 404),
                           ("SPACE_SOURCE_CHANGED_SINCE_CENSUS", 409),
                           ("ANONYMOUS_HUB_SPACE_INFO_UNAVAILABLE", 503)):
        with patch.object(app, "observe_public_space_runtime",
                          side_effect=runtime.RuntimeObservationError(reason, status)):
            response = client.get("/api/atlas/space-runtime/anatomy")
        assert response.status_code == status
        doc = response.json()
        assert doc["state"] == "UNAVAILABLE"
        assert doc["reason_code"] == reason
        assert doc["provider_stage"] is None
        assert "space_id" not in doc
        assert doc["execution_authorized"] is False


def test_unexpected_provider_exception_never_leaks_secrets():
    with patch.object(app, "observe_public_space_runtime",
                      side_effect=RuntimeError("SECRET_X_TOKEN_RAW_PROVIDER_123")):
        response = TestClient(app.app).get("/api/atlas/space-runtime/anatomy")
    assert response.status_code == 503
    assert "SECRET_X_TOKEN" not in response.text
    assert response.json()["provider_stage"] is None
