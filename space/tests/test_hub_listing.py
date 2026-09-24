"""Real JSON decoding regression coverage for the Hub's array API contracts."""
import io
import json
import os

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import pytest
from fastapi.testclient import TestClient

import app as constellation


def _response(value):
    response = io.BytesIO(json.dumps(value).encode())
    response.headers = {"Content-Type": "application/json"}
    return response


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(constellation, "CACHE", {})


def test_estate_inventory_decodes_hub_arrays(monkeypatch):
    def upstream(request, timeout):
        if "api.github.com" in request.full_url:
            return _response({"total_count": 117})
        return _response([{"id": "SZLHOLDINGS/example"}])

    monkeypatch.setattr(constellation.urllib.request, "urlopen", upstream)
    with TestClient(constellation.app) as client:
        response = client.get("/api/estates")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "MEASURED"
    assert body["github"]["org_repos_total"] == 117
    for kind in ("spaces", "models", "datasets"):
        assert body["huggingface"][kind] == {"count": 1, "names": ["example"]}


def test_kernel_and_khipu_listings_decode_hub_arrays(monkeypatch):
    monkeypatch.setitem(constellation.MANIFEST, "kernel_line", ["example-kernel"])
    monkeypatch.setattr(
        constellation.urllib.request,
        "urlopen",
        lambda *a, **k: _response([
            {"id": "SZLHOLDINGS/example-kernel", "downloads": 3},
            {"id": "SZLHOLDINGS/khipu-example", "downloads": 7},
        ]),
    )
    kernels = constellation.kernel_line()
    assert kernels["state"] == "MEASURED"
    assert kernels["kernels"][0]["kernel"] == "example-kernel"
    assert kernels["org_models_total"] == 2
    khipu = constellation.khipu_line()
    assert khipu["state"] == "MEASURED"
    assert khipu["total_downloads"] == 7


@pytest.mark.parametrize("rows", [{"error": "unavailable"}, [None], [{}], [{"id": 42}], [{"id": " "}]])
def test_malformed_listings_fail_closed(monkeypatch, rows):
    monkeypatch.setattr(constellation.urllib.request, "urlopen", lambda *a, **k: _response(rows))
    assert constellation.kernel_line()["state"] == "UNAVAILABLE"
    assert constellation.khipu_line()["state"] == "UNAVAILABLE"
    estate = constellation._measure_org()
    assert estate["state"] == "PARTIAL"
    assert all(value["state"] == "UNAVAILABLE" for value in estate["huggingface"].values())


def test_object_consumers_still_reject_arrays(monkeypatch):
    monkeypatch.setattr(constellation.urllib.request, "urlopen", lambda *a, **k: _response([]))
    with pytest.raises(ValueError, match="JSON object required"):
        constellation._fetch_json("https://example.test/object")


def test_empty_hub_listing_is_valid(monkeypatch):
    monkeypatch.setattr(constellation.urllib.request, "urlopen", lambda *a, **k: _response([]))
    assert constellation._fetch_hub_listing("https://example.test/list") == []


def test_hub_listing_retains_response_bound(monkeypatch):
    monkeypatch.setattr(constellation, "MAX_PROXY_RESPONSE_BYTES", 10)
    monkeypatch.setattr(constellation.urllib.request, "urlopen", lambda *a, **k: _response([{"id": "SZLHOLDINGS/example"}]))
    with pytest.raises(ValueError, match="exceeds response bound"):
        constellation._fetch_hub_listing("https://example.test/list")


def test_hub_listing_rejects_non_finite_json(monkeypatch):
    monkeypatch.setattr(constellation.urllib.request, "urlopen", lambda *a, **k: _response([{"id": "SZLHOLDINGS/example", "downloads": float("nan") }]))
    with pytest.raises(ValueError, match="non-finite JSON"):
        constellation._fetch_hub_listing("https://example.test/list")
