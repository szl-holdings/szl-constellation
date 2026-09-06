import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import pytest
from fastapi.testclient import TestClient

import app as constellation


def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _chain_receipt(metrics, *, previous=constellation.GENESIS):
    payload = {
        "results": [
            {
                "engine": "shared-engine",
                "runs": 3,
                "metrics": metrics,
            }
        ]
    }
    chain_hash = hashlib.sha256((previous + _canon(payload)).encode()).hexdigest()
    return {**payload, "prev_hash": previous, "chain_hash": chain_hash}


@pytest.fixture()
def client():
    with TestClient(constellation.app, follow_redirects=True) as test_client:
        yield test_client


def test_entrypoint_preserves_core_routes(client):
    root = client.get("/")
    assert root.status_code == 200
    assert "SZL CONSTELLATION" in root.text
    assert client.get("/static/estates.json").status_code == 200
    assert client.get("/static/verticals.json").status_code == 200
    assert client.get("/static/app.py").status_code == 404
    assert client.get("/panels").status_code == 200
    status = client.get("/api/panels/status")
    assert status.status_code == 200
    assert status.json()["panels"] == "MOUNTED"


def test_health_ready_and_exact_source_contract(client, monkeypatch):
    monkeypatch.setattr(
        constellation,
        "_provider_runtime",
        lambda: {"revision": "a" * 40, "stage": "RUNNING", "replicas": 1, "domain_stage": "READY"},
    )
    monkeypatch.setattr(
        constellation,
        "_remote_app_sha256",
        lambda revision: (constellation._local_app_sha256(), f"https://example.test/{revision}/app.py"),
    )
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert len(health.json()["app_sha256"]) == 64

    source = client.get("/api/source")
    assert source.status_code == 200
    assert source.json()["state"] == "MEASURED"
    assert source.json()["source_revision"] == "a" * 40
    assert source.json()["immutable_source"].endswith(("a" * 40) + "/app.py")
    assert source.json()["app_bytes_match"] is True

    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    assert all(ready.json()["checks"].values())
    assert ready.json()["listener_contract"]["state"] == "METHOD"
    assert ready.json()["listener_contract"]["uvicorn_run_calls"] == 1


def test_runtime_has_exactly_one_listener_and_ssr_is_disabled():
    source = Path(constellation.__file__).read_text(encoding="utf-8")
    assert source.count("uvicorn.run(") == 1
    assert ".launch(" not in source
    assert "ssr_mode=False" in source


def test_sentra_proxies_fail_closed_on_invalid_json_contracts(monkeypatch):
    monkeypatch.setattr(constellation, "_fetch_json", lambda *args, **kwargs: {"status": "ok"})
    gate = constellation.sentra_gate_proxy("0.9,0.95", "1,1", 0.97)
    yawar = constellation.sentra_yawar_proxy("[]")
    planes = constellation.sentra_planes()
    assert gate["state"] == "UNAVAILABLE"
    assert yawar["state"] == "UNAVAILABLE"
    assert planes["state"] == "UNAVAILABLE"


def test_crosscheck_request_body_is_bounded(client):
    response = client.post(
        "/api/crosscheck",
        content=b'{"a":[],"b":[],"padding":"' + b"x" * 1_000_001 + b'"}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["state"] == "BLOCKED"
    assert response.json()["error"] == "REQUEST_TOO_LARGE"


def test_crosscheck_stream_is_bounded_when_content_length_lies(client):
    def chunks():
        yield b'{"a":[],"b":[],"padding":"'
        yield b"x" * 1_000_001
        yield b'"}'

    response = client.post(
        "/api/crosscheck",
        content=chunks(),
        headers={"content-type": "application/json", "content-length": "1"},
    )
    assert response.status_code == 413
    assert response.json()["state"] == "BLOCKED"
    assert response.json()["error"] == "REQUEST_TOO_LARGE"


def test_crosscheck_rejects_negative_content_length(client):
    response = client.post(
        "/api/crosscheck",
        content=b"{}",
        headers={"content-type": "application/json", "content-length": "-1"},
    )
    assert response.status_code == 400
    assert response.json() == {"state": "BLOCKED", "error": "INVALID_CONTENT_LENGTH"}


class _FakeResponse:
    def __init__(self, content, content_type="application/json"):
        self.content = content
        self.headers = {"Content-Type": content_type}

    def read(self, size=-1):
        return self.content if size < 0 else self.content[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


@pytest.mark.parametrize(
    "content,content_type",
    [
        (b"not-json", "application/json"),
        (b"[]", "application/json"),
        (b'{"ok":true}', "text/html"),
        (b'{' + b'"x":"' + b"y" * 1_000_001 + b'"}', "application/json"),
        (b'{"decision":"allow","fail_closed":true,"score":NaN}', "application/json"),
    ],
    ids=("malformed", "nonobject", "wrong-content-type", "oversized", "non-finite"),
)
def test_fetch_json_rejects_malformed_nonobject_wrong_type_and_oversized(
    monkeypatch, content, content_type
):
    monkeypatch.setattr(
        constellation.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(content, content_type),
    )
    with pytest.raises(ValueError):
        constellation._fetch_json("https://example.test")


@pytest.mark.parametrize(
    "scores,weights,threshold",
    [
        ("NaN", "1", 0.97),
        ("0.9", "Infinity", 0.97),
        ("0.9", "1", float("-inf")),
        ("", "", 0.97),
        ("1.1", "1", 0.97),
        ("0.9,0.8", "1", 0.97),
    ],
)
def test_sentra_gate_rejects_invalid_or_non_finite_inputs_before_upstream(
    monkeypatch, scores, weights, threshold
):
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("upstream must not be called")

    monkeypatch.setattr(constellation.urllib.request, "urlopen", fail_if_called)
    result = constellation.sentra_gate_proxy(scores, weights, threshold)
    assert result["state"] == "UNAVAILABLE"
    assert called is False


def test_consoles_have_exactly_one_crosscheck_tab_and_expected_controls():
    config = constellation.build_consoles().get_config_file()
    crosscheck_tabs = [
        component
        for component in config["components"]
        if component["type"] == "tabitem"
        and component.get("props", {}).get("label") == "Crosscheck"
    ]
    assert len(crosscheck_tabs) == 1

    props = [component.get("props", {}) for component in config["components"]]
    assert sum(p.get("label") == "Receipt chain A (JSON)" for p in props) == 1
    assert sum(p.get("label") == "Receipt chain B (JSON)" for p in props) == 1
    assert sum(p.get("label") == "Relative tolerance" for p in props) == 1
    assert sum(p.get("label") == "cross-implementation verdict" for p in props) == 1


def test_crosscheck_api_returns_consistent_verdict_with_recomputable_receipt(client):
    chain_a = [_chain_receipt({"latency_ms": 10.0, "throughput": 5.0})]
    chain_b = [_chain_receipt({"latency_ms": 10.05, "throughput": 5.0})]

    response = client.post(
        "/api/crosscheck",
        json={"a": chain_a, "b": chain_b, "rel_tol": 0.01},
    )

    assert response.status_code == 200
    body = response.json()
    receipt = body.pop("receipt")
    assert body["state"] == "MEASURED"
    assert body["verdict"] == "CONSISTENT"
    assert receipt["sha256"] == hashlib.sha256(_canon(body).encode()).hexdigest()
    assert receipt["signature"].startswith("UNSIGNED_HONEST")


def test_crosscheck_api_reports_divergence_and_invalid_chains_without_false_green(client):
    chain_a = [_chain_receipt({"latency_ms": 10.0})]
    chain_b = [_chain_receipt({"latency_ms": 12.0})]
    divergent = client.post(
        "/api/crosscheck",
        json={"a": chain_a, "b": chain_b, "rel_tol": 0.01},
    )
    assert divergent.status_code == 200
    assert divergent.json()["verdict"] == "DIVERGENT"
    assert divergent.json()["lanes"][0]["worst_metric"] == "latency_ms"

    tampered = [{**chain_a[0], "chain_hash": "0" * 64}]
    invalid = client.post(
        "/api/crosscheck",
        json={"a": tampered, "b": chain_b},
    )
    assert invalid.status_code == 200
    assert invalid.json()["state"] == "INVALID"
    assert "receipt" in invalid.json()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_crosscheck_rejects_non_finite_metrics_without_false_green(client, value):
    chain = [_chain_receipt({"latency_ms": value})]
    direct = constellation.crosscheck_chains(_canon(chain), _canon(chain))
    assert direct["state"] == "INVALID"
    assert "non-finite" in direct["detail"]

    response = client.post(
        "/api/crosscheck",
        content=json.dumps({"a": chain, "b": chain}),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json() == {"state": "BLOCKED", "error": "INVALID_REQUEST"}


def test_crosscheck_deeply_nested_json_fails_closed(client):
    nested = b"[" * 2_000 + b"]" * 2_000
    response = client.post(
        "/api/crosscheck",
        content=b'{"a":' + nested + b',"b":[]}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json() == {"state": "BLOCKED", "error": "INVALID_REQUEST"}


def test_crosscheck_finite_extremes_diverge_without_overflow(client):
    chain_a = [_chain_receipt({"signed_metric": 1e308})]
    chain_b = [_chain_receipt({"signed_metric": -1e308})]
    direct = constellation.crosscheck_chains(_canon(chain_a), _canon(chain_b))
    assert direct["state"] == "MEASURED"
    assert direct["verdict"] == "DIVERGENT"
    assert direct["lanes"][0]["max_rel_delta"] == 2.0
    response = client.post("/api/crosscheck", json={"a": chain_a, "b": chain_b})
    assert response.status_code == 200
    assert response.json()["verdict"] == "DIVERGENT"
    assert response.json()["lanes"][0]["max_rel_delta"] == 2.0


def test_crosscheck_disjoint_metrics_are_incomparable(client):
    chain_a = [_chain_receipt({"latency": 1.0})]
    chain_b = [_chain_receipt({"throughput": 1.0})]
    direct = constellation.crosscheck_chains(_canon(chain_a), _canon(chain_b))
    assert direct["verdict"] == "INCOMPARABLE"
    response = client.post("/api/crosscheck", json={"a": chain_a, "b": chain_b})
    assert response.status_code == 200
    assert response.json()["verdict"] == "INCOMPARABLE"


@pytest.mark.parametrize("results", [3, "malformed", [3]])
def test_crosscheck_invalid_results_shape_fails_closed(client, results):
    payload = {"results": results}
    chain = [{**payload, "prev_hash": constellation.GENESIS,
              "chain_hash": hashlib.sha256((constellation.GENESIS + _canon(payload)).encode()).hexdigest()}]
    direct = constellation.crosscheck_chains(_canon(chain), _canon(chain))
    assert direct["state"] == "INVALID"
    response = client.post("/api/crosscheck", json={"a": chain, "b": chain})
    assert response.status_code == 200
    assert response.json()["state"] == "INVALID"


def test_current_family_console_routes_preserved(client):
    assert client.get("/c2").status_code == 200
    families = client.get("/api/families")
    assert families.status_code == 200
    assert families.json()["families"] == constellation.VERTICALS["family_flagships"]
    assert client.get("/api/constellation/manifest").json()["manifest"]["family_flagships"]


def test_console_mount_failure_remains_visible(monkeypatch):
    def fail_mount():
        raise RuntimeError("synthetic test mount failure")

    monkeypatch.setattr(constellation, "build_consoles", fail_mount)
    with TestClient(constellation.create_app()) as failed:
        assert "CONSOLES UNAVAILABLE" in failed.get("/panels").text
        assert failed.get("/api/panels/status").json()["panels"] == "MOUNT_FAILED"


@pytest.mark.parametrize(
    "payload",
    [
        {"a": [], "rel_tol": 0.01},
        {"a": ["not-a-receipt"], "b": []},
        {"a": [], "b": [], "rel_tol": -0.001},
        {"a": [], "b": [], "rel_tol": 1.001},
        {"a": [], "b": [], "padding": "not allowed"},
    ],
)
def test_crosscheck_api_rejects_malformed_request_shapes(client, payload):
    assert client.post("/api/crosscheck", json=payload).status_code == 422
