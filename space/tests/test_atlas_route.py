"""Actual FastAPI mount and read-only public atlas contract (offline fixtures)."""
from __future__ import annotations
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

import app


def test_atlas_static_routes_are_additive_and_local():
    client=TestClient(app.app)
    page=client.get("/atlas/")
    assert page.status_code == 200
    assert "ATLAS" in page.text
    assert 'src="/atlas/atlas.js"' in page.text
    assert "no private resources are listed" in page.text.lower()
    assert client.get("/atlas/atlas.js").status_code == 200
    assert client.get("/atlas/vendor/three.module.js").status_code == 200
    assert client.get("/atlas/vendor/three.core.js").status_code == 200
    assert client.get("/atlas/vendor/OrbitControls.js").status_code == 200
    assert client.get("/atlas/atlas.css").status_code == 200
    assert client.get("/atlas/vendor/THREE-LICENSE.txt").status_code == 200
    # Legacy root and consoles are not shadowed by the new static mount.
    assert client.get("/").status_code == 200
    assert client.get("/healthz").status_code == 200


def test_atlas_api_failure_denies_stale_data_and_upstream_errors():
    client=TestClient(app.app)
    with patch.object(app,"cached_public_atlas",side_effect=RuntimeError(
            "HF_TOKEN_PRIVATE_DO_NOT_LEAK")):
        resp=client.get("/api/atlas/public")
    assert resp.status_code == 503
    assert resp.json()["state"] == "UNAVAILABLE"
    assert resp.json()["production_qualified"] is False
    assert resp.json()["execution_authorized"] is False
    assert "PRIVATE_DO_NOT_LEAK" not in resp.text
    assert resp.headers["cache-control"] == "no-store"


def test_atlas_api_success_keeps_readonly_source_fields():
    result={"schema":"szl.public-hub-holographic-atlas/v1",
            "state":"OBSERVED_PUBLIC_HUB_METADATA",
            "scope":"ANONYMOUS_PUBLIC_HUB_ONLY",
            "counts":{"space":0,"model":0,"dataset":0},
            "declared_verticals":0,
            "nodes":[],"links":[],"private_assets_excluded":True,
            "runtime_readiness":"NOT_EVALUATED",
            "production_qualified":False,"execution_authorized":False,
            "observation_sha256":"f"*64}
    client=TestClient(app.app)
    with patch.object(app,"cached_public_atlas",return_value=result):
        resp=client.get("/api/atlas/public")
    assert resp.status_code == 200
    assert resp.json()==result
    assert resp.headers["cache-control"] == "no-store"
    assert resp.headers["x-content-type-options"] == "nosniff"
