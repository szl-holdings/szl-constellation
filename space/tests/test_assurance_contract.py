"""Fail-closed coverage for the reported, read-only assurance manifest."""

from copy import deepcopy
import hashlib
import json
import os
from urllib.error import URLError

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import pytest
from fastapi.testclient import TestClient

import app as constellation


VERIFIER = "https://szlholdings-a11oy.hf.space/api/a11oy/v1/verify/receipt"
VERIFIER_UI = "https://szlholdings-a11oy.hf.space/verify"


def _envelope():
    return {
        "status": "REACHABLE",
        "http_status": 200,
        "receipt_verified": False,
        "source": VERIFIER,
        "data": {
            "schema": "szl.public-receipt-verifier/manifest/v1",
            "state": "LIVE",
            "try": {
                "method": "POST",
                "endpoint": "/api/a11oy/v1/verify/receipt",
            },
            "evidence": ["signature", "payload_digest", "hash_chain"],
            "reproduce": {"human_ui": "/verify"},
        },
    }


def _assert_no_verification_or_approval(result, state):
    assert result["state"] == state
    assert result["receipt_verified"] is False
    assert result["approval_granted"] is False


def _replace(payload, path, value):
    parent = payload
    for name in path[:-1]:
        parent = parent[name]
    parent[path[-1]] = value


def test_minimal_manifest_is_reported_and_fetches_only_fixed_read_endpoint(monkeypatch):
    calls = []

    def fetch(url, *args, **kwargs):
        calls.append((url, args, kwargs))
        return _envelope()

    monkeypatch.setattr(constellation, "_fetch_json", fetch)
    result = constellation.assurance_contract()

    _assert_no_verification_or_approval(result, "REPORTED")
    assert constellation.ASSURANCE_VERIFIER == VERIFIER
    assert constellation.ASSURANCE_UI == VERIFIER_UI
    assert result["verifier"] == VERIFIER
    assert result["verifier_ui"] == VERIFIER_UI
    assert len(calls) == 1
    url, args, kwargs = calls[0]
    assert url == constellation.SENTRA + "/api/live"
    assert args == ()
    assert kwargs.get("payload") is None

    receipt = result.pop("receipt")
    expected = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    assert receipt["sha256"] == expected
    assert receipt["signature"].startswith("UNSIGNED_HONEST")


@pytest.mark.parametrize("payload", [None, [], "LIVE", 0, True, {}])
def test_nonobject_or_empty_envelopes_fail_closed(monkeypatch, payload):
    monkeypatch.setattr(constellation, "_fetch_json", lambda *a, **k: payload)
    _assert_no_verification_or_approval(constellation.assurance_contract(), "UNAVAILABLE")


def test_public_failure_does_not_expose_exception_details(monkeypatch):
    private_detail = "upstream-internal.test/private/path?token=synthetic-secret"

    def fail(*args, **kwargs):
        raise ValueError(private_detail)

    monkeypatch.setattr(constellation, "_fetch_json", fail)
    response = TestClient(constellation.app).get("/api/assurance/status")
    assert response.status_code == 503
    result = response.json()
    _assert_no_verification_or_approval(result, "UNAVAILABLE")
    assert result["detail"] == "upstream assurance contract unavailable or incompatible"
    assert private_detail not in response.text
    assert "synthetic-secret" not in response.text


@pytest.mark.parametrize(
    "path",
    [
        ("status",),
        ("http_status",),
        ("receipt_verified",),
        ("source",),
        ("data",),
        ("data", "schema"),
        ("data", "state"),
        ("data", "try"),
        ("data", "try", "method"),
        ("data", "try", "endpoint"),
        ("data", "evidence"),
        ("data", "reproduce"),
        ("data", "reproduce", "human_ui"),
    ],
    ids=lambda path: ".".join(path),
)
def test_every_contract_field_is_required(monkeypatch, path):
    payload = _envelope()
    parent = payload
    for name in path[:-1]:
        parent = parent[name]
    del parent[path[-1]]
    monkeypatch.setattr(constellation, "_fetch_json", lambda *a, **k: payload)
    _assert_no_verification_or_approval(constellation.assurance_contract(), "UNAVAILABLE")


@pytest.mark.parametrize(
    "path,value",
    [
        (("status",), "MEASURED"),
        (("status",), "PASS"),
        (("http_status",), 503),
        (("http_status",), "200"),
        (("http_status",), 200.0),
        (("http_status",), True),
        (("receipt_verified",), True),
        (("receipt_verified",), 0),
        (("receipt_verified",), "false"),
        (("receipt_verified",), None),
        (("source",), VERIFIER.replace("https:", "http:")),
        (("source",), "https://example.test/api/a11oy/v1/verify/receipt"),
        (("source",), VERIFIER + "?redirect=https://example.test"),
        (("source",), VERIFIER + "/"),
        (("data",), []),
        (("data",), None),
        (("data", "schema"), "szl.public-receipt-verifier/manifest/v2"),
        (("data", "state"), "PASS"),
        (("data", "try"), []),
        (("data", "try", "method"), "GET"),
        (("data", "try", "endpoint"), VERIFIER),
        (("data", "try", "endpoint"), "/api/sentra/gate"),
        (("data", "try", "endpoint"), "//example.test/verify"),
        (("data", "reproduce"), []),
        (("data", "reproduce", "human_ui"), VERIFIER_UI),
        (("data", "reproduce", "human_ui"), "//example.test/verify"),
        (("data", "reproduce", "human_ui"), "/verify?redirect=https://example.test"),
        (("data", "evidence"), []),
        (("data", "evidence"), "signature,payload_digest,hash_chain"),
        (("data", "evidence"), {"signature": True, "payload_digest": True, "hash_chain": True}),
        (("data", "evidence"), ["signature", "payload_digest"]),
        (("data", "evidence"), ["signature", "payload_digest", "hash_chain", "approval"]),
        (("data", "evidence"), ["signature", "signature", "payload_digest", "hash_chain"]),
        (("data", "evidence"), ["signature", "signature", "hash_chain"]),
        (("data", "evidence"), ["signature", "payload_digest", {}]),
    ],
)
def test_mismatched_contract_values_fail_closed(monkeypatch, path, value):
    payload = _envelope()
    _replace(payload, path, value)
    monkeypatch.setattr(constellation, "_fetch_json", lambda *a, **k: payload)
    _assert_no_verification_or_approval(constellation.assurance_contract(), "UNAVAILABLE")


@pytest.mark.parametrize("error", [TimeoutError("timeout"), URLError("offline"), ValueError("malformed JSON"), RecursionError("deep JSON")])
def test_unavailable_or_malformed_upstream_fails_closed(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(constellation, "_fetch_json", fail)
    _assert_no_verification_or_approval(constellation.assurance_contract(), "UNAVAILABLE")


def test_additional_upstream_claims_never_become_local_approval(monkeypatch):
    payload = deepcopy(_envelope())
    payload.update({"state": "MEASURED", "approval_granted": True, "verdict": "PASS"})
    payload["data"]["approval_granted"] = True
    monkeypatch.setattr(constellation, "_fetch_json", lambda *a, **k: payload)
    _assert_no_verification_or_approval(constellation.assurance_contract(), "REPORTED")


def test_evidence_order_is_not_part_of_the_contract(monkeypatch):
    payload = _envelope()
    payload["data"]["evidence"].reverse()
    monkeypatch.setattr(constellation, "_fetch_json", lambda *a, **k: payload)
    _assert_no_verification_or_approval(constellation.assurance_contract(), "REPORTED")


@pytest.mark.parametrize("available,expected_code", [(True, 200), (False, 503)])
def test_assurance_api_status_matches_contract_availability(monkeypatch, available, expected_code):
    monkeypatch.setattr(
        constellation, "_fetch_json", lambda *a, **k: _envelope() if available else {}
    )
    with TestClient(constellation.app) as client:
        response = client.get("/api/assurance/status")
    assert response.status_code == expected_code
    _assert_no_verification_or_approval(response.json(), "REPORTED" if available else "UNAVAILABLE")


def test_retired_functions_and_route_make_no_upstream_calls(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("retired assurance controls must never call an upstream")

    monkeypatch.setattr(constellation, "_fetch_json", forbidden)
    monkeypatch.setattr(constellation.urllib.request, "urlopen", forbidden)
    retired = [
        constellation.sentra_gate_proxy("0.9,0.95", "1,1", 0.97),
        constellation.sentra_yawar_proxy("[]"),
        constellation.sentra_planes(),
    ]
    with TestClient(constellation.app) as client:
        response = client.get("/api/sentra/planes")
    assert response.status_code == 410
    retired.append(response.json())
    for result in retired:
        _assert_no_verification_or_approval(result, "UNAVAILABLE")
        assert result["reason"] == "RETIRED_CONTRACT"
    assert calls == []


def _layout_subtree(node, component_id):
    if node.get("id") == component_id:
        return node
    for child in node.get("children", []):
        found = _layout_subtree(child, component_id)
        if found is not None:
            return found
    return None


def _layout_ids(node):
    return {node["id"]}.union(*(_layout_ids(child) for child in node.get("children", [])))


def test_sentra_tab_exposes_only_read_contract_and_canonical_verifier_controls():
    config = constellation.build_consoles().get_config_file()
    tabs = [
        component for component in config["components"]
        if component["type"] == "tabitem"
        and component.get("props", {}).get("label") == "Sentra Assurance"
    ]
    assert len(tabs) == 1
    subtree = _layout_subtree(config["layout"], tabs[0]["id"])
    assert subtree is not None
    component_ids = _layout_ids(subtree)
    scoped = [component for component in config["components"] if component["id"] in component_ids]
    assert not any(component["type"] in {"textbox", "slider"} for component in scoped)
    buttons = [component for component in scoped if component["type"] == "button"]
    assert {button["props"]["value"] for button in buttons} == {
        "Read current assurance contract", "Open canonical receipt verifier"
    }
    link = next(button for button in buttons if button["props"]["value"] == "Open canonical receipt verifier")
    assert link["props"]["link"] == VERIFIER_UI
    read = next(button for button in buttons if button["props"]["value"] == "Read current assurance contract")
    listeners = [
        dependency for dependency in config["dependencies"]
        if any(target[0] == read["id"] for target in dependency.get("targets", []))
    ]
    assert len(listeners) == 1
    assert listeners[0]["inputs"] == []
