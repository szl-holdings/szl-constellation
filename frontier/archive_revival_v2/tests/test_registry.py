# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as service  # noqa: E402
import registry as lineage  # noqa: E402

client = TestClient(service.app)


def test_registry_exact_counts_and_source_owner_allowlist() -> None:
    value = lineage.load_registry()
    assert value["counts"] == {"source_owner": 4, "consolidate": 24, "historical": 6, "total": 34}
    rows = value["repositories"]
    assert len(rows) == len({row["name"] for row in rows}) == 34
    assert sorted(row["name"] for row in rows if row["disposition"] == "SOURCE_OWNER") == [
        "szl-atelier",
        "szl-mesh",
        "szl-router",
        "uds-bundles",
    ]
    assert sum(row["disposition"] == "CONSOLIDATE" for row in rows) == 24
    assert sum(row["disposition"] == "HISTORICAL" for row in rows) == 6


def test_disposition_invariants() -> None:
    rows = lineage.load_registry()["repositories"]
    for row in rows:
        assert row["provider_state"] == "UNAVAILABLE_NOT_MEASURED"
        if row["disposition"] == "SOURCE_OWNER":
            assert row["successor"] == row["name"]
            assert row["expected_archived"] is False
            assert row["immutable_history"] is False
        elif row["disposition"] == "CONSOLIDATE":
            assert row["successor"]
            assert row["expected_archived"] is True
            assert row["immutable_history"] is False
        else:
            assert row["successor"] is None
            assert row["expected_archived"] is True
            assert row["immutable_history"] is True


def test_registry_receipt_is_deterministic() -> None:
    first = lineage.public_registry()
    second = lineage.public_registry()
    assert first == second
    unsigned = lineage.load_registry()
    expected = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert first["receipt_sha256"] == expected
    assert first["provider_readback"] == "UNAVAILABLE_NOT_PERFORMED"


def test_registry_rejects_duplicate_and_drifted_rows(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema":"one","schema":"two"}', encoding="utf-8")
    with pytest.raises(lineage.RegistryError, match="duplicate JSON key"):
        lineage.load_registry(duplicate)

    drifted = lineage.load_registry()
    drifted["counts"] = {"source_owner": 5, "consolidate": 23, "historical": 6, "total": 34}
    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(lineage.RegistryError, match="declared counts"):
        lineage.load_registry(drift_path)


def test_health_readiness_and_source(monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_REVISION", "c" * 40)
    monkeypatch.setenv("GH_TOKEN", "ghp_" + "x" * 40)
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").status_code == 200
    response = client.get("/api/source")
    assert response.status_code == 200
    assert "ghp_" not in response.text
    payload = response.json()
    assert payload["source"] == {"state": "MEASURED", "revision": "c" * 40}
    assert payload["mutation_authority"] is False
    assert payload["repository_admin_authority"] is False
    assert payload["hugging_face_write_authority"] is False
    assert payload["secrets_recorded"] is False


def test_registry_api_filters_without_mutation() -> None:
    full = client.get("/api/archive-revival")
    assert full.status_code == 200
    assert full.json()["returned_count"] == 34
    assert full.json()["provider_readback"] == "UNAVAILABLE_NOT_PERFORMED"
    assert full.json()["mutation_authority"] is False

    restored = client.get("/api/archive-revival", params={"disposition": "SOURCE_OWNER"})
    assert restored.status_code == 200
    assert restored.json()["returned_count"] == 4

    a11oy = client.get("/api/archive-revival", params={"successor": "a11oy"})
    assert a11oy.status_code == 200
    assert sorted(row["name"] for row in a11oy.json()["repositories"]) == ["szl-experiments", "szl-organ-integrity"]

    search = client.get("/api/archive-revival", params={"q": "air-gap"})
    assert search.status_code == 200
    assert any(row["name"] == "uds-bundles" for row in search.json()["repositories"])

    assert client.get("/api/archive-revival", params={"disposition": "DELETE"}).status_code == 422
    assert client.get("/api/archive-revival", params={"q": "x" * 65}).status_code == 422


def test_repository_detail_is_local_and_fail_closed() -> None:
    response = client.get("/api/archive-revival/uds-bundles")
    assert response.status_code == 200
    payload = response.json()
    assert payload["repository"]["disposition"] == "SOURCE_OWNER"
    assert payload["live_archive_state"] == "UNAVAILABLE_NOT_MEASURED"
    assert payload["hub_publication_state"] == "UNAVAILABLE_NOT_MEASURED"
    assert payload["runtime_state"] == "UNAVAILABLE_NOT_MEASURED"
    assert client.get("/api/archive-revival/not-real").status_code == 404
    assert client.get("/api/archive-revival/../../etc/passwd").status_code == 404


def test_security_headers_and_local_frontend() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["x-frame-options"] == "DENY"
    assert "connect-src 'self'" in response.headers["content-security-policy"]
    html = response.text
    assert "http://" not in html
    assert "https://" not in html
    assert "<iframe" not in html
    assert "localStorage" not in html
    assert "sessionStorage" not in html
    javascript = client.get("/app.js")
    assert javascript.status_code == 200
    assert "innerHTML" not in javascript.text
    assert "insertAdjacentHTML" not in javascript.text
    assert "fetch(`https://" not in javascript.text
    assert client.get("/styles.css").status_code == 200


def test_no_mutating_http_routes() -> None:
    methods = {
        method
        for route in service.app.routes
        for method in getattr(route, "methods", set())
        if not str(getattr(route, "path", "")).startswith("/api/docs")
    }
    assert methods <= {"GET", "HEAD"}
