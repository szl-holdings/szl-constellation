"""Native assets are a bounded part of the established source package."""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

import app as constellation
import presentation

ROOT = Path(__file__).resolve().parents[2]


class Resources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.resources = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        key = "href" if tag == "link" else "src"
        if tag in {"script", "link", "img"} and attrs.get(key, "").startswith("/assets/szl/"):
            self.resources.append((tag, attrs[key], "defer" in attrs))


def test_all_actual_pages_reference_served_native_assets():
    expected = {
        "/assets/szl/szl-tokens.css",
        "/assets/szl/native.css",
        "/assets/szl/native.js",
        "/assets/szl/szl-icon-32.svg",
    }
    with TestClient(constellation.app) as client:
        for route in ("/", "/c2", "/holo/demo.html"):
            response = client.get(route)
            assert response.status_code == 200
            parser = Resources()
            parser.feed(response.text)
            assert {item[1] for item in parser.resources} == expected
            assert ("script", "/assets/szl/native.js", True) in parser.resources
        for route, (name, content_type) in presentation.ASSETS.items():
            response = client.get(route)
            assert response.status_code == 200
            assert response.content == (presentation.ROOT / name).read_bytes()
            assert response.headers["content-type"] == content_type
            assert response.headers["x-content-type-options"] == "nosniff"
        for route in ("/assets/szl/app.py", "/assets/szl/../app.py", "/assets/szl/estates.json", "/assets/szl/%2e%2e/app.py"):
            assert client.get(route).status_code == 404


def test_projection_is_exact_and_mounted_console_uses_same_tokens():
    record = json.loads((presentation.ROOT / "PROJECTION.json").read_text())
    assert record["source_revision"] == "27d12e77fc0f9f1a0e5fae8b34adf2380d51d070"
    assert record["files"] == {
        "szl-tokens.css": {
            "bytes": 9559,
            "sha256": "81f7c9baeef0b435e6e3f9d0c4e0d70e40fa17df5d1f30697f623cd3ef5f8eab",
        },
        "szl-icon-32.svg": {
            "bytes": 2969,
            "sha256": "6e2b7d72a3af3d9602b79de41df0194ede6496a9661f057108ec224c0efc92e6",
        },
    }
    for name, digest in record["files"].items():
        data = (presentation.ROOT / name).read_bytes()
        assert len(data) == digest["bytes"]
        assert hashlib.sha256(data).hexdigest() == digest["sha256"]
    assert constellation.CSS.startswith((presentation.ROOT / "szl-tokens.css").read_text())


@pytest.mark.parametrize("variant", ["missing", "symlink", "directory", "oversized"])
def test_asset_boundaries_fail_without_serving_other_files(tmp_path, monkeypatch, variant):
    path = tmp_path / "native.css"
    if variant == "symlink":
        outside = tmp_path / "outside.txt"
        outside.write_text("private sentinel")
        path.symlink_to(outside)
    elif variant == "directory":
        path.mkdir()
    elif variant == "oversized":
        path.write_bytes(b"x" * (presentation.MAX_ASSET_BYTES + 1))
    monkeypatch.setattr(presentation, "ROOT", tmp_path)
    with TestClient(constellation.app) as client:
        response = client.get("/assets/szl/native.css")
        assert response.status_code == 503
        assert response.text == "Presentation asset unavailable"


def test_existing_publisher_covers_every_native_byte_and_detects_tampering():
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import publish_constellation as publisher

    stage, holder, managed = publisher.stage_tree("a" * 40, "12345")
    try:
        assert len(managed) <= constellation.MAX_SOURCE_BINDING_FILES
        assert "presentation.py" in managed
        for name, _ in presentation.ASSETS.values():
            relative = "presentation/" + name
            assert relative in managed
            data = (stage / relative).read_bytes()
            assert data == (presentation.ROOT / name).read_bytes()
            assert managed[relative]["sha256"] == hashlib.sha256(data).hexdigest()
        binding = constellation.publisher_source_binding(stage)
        assert binding["state"] == "LOCAL_BYTES_VERIFIED"
        assert binding["source_authority"] == "PUBLISHER_DECLARED"
        assert binding["github_attestation"] == "NOT_PERFORMED_AT_RUNTIME"
        (stage / "presentation/native.css").write_bytes(b"tampered")
        invalid = constellation.publisher_source_binding(stage)
        assert invalid["state"] == "UNAVAILABLE"
        assert invalid["source_revision"] == "UNAVAILABLE"
    finally:
        holder.cleanup()
