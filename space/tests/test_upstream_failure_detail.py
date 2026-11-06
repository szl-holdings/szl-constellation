"""Upstream failures reach clients as an honest state plus an exception class name.

Every live-measurement surface (REST route or console handler) that calls
GitHub, the Hub or an estate runtime reports UNAVAILABLE/PARTIAL when the call
fails. The exception text itself, which can carry upstream URLs, local paths or
response bodies, never reaches the payload (CWE-209, CodeQL
py/stack-trace-exposure).
"""
import json
import os
import urllib.error

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import pytest
from fastapi.testclient import TestClient

import app as constellation

PRIVATE_TEXT = "SENTINEL-0d9e /srv/upstream/private.cfg?token=never-shown"
PROBED_VERTICALS = sorted(v["id"] for v in constellation.VERTICALS["verticals"] if v.get("live"))


@pytest.fixture(autouse=True)
def failing_upstream(monkeypatch):
    monkeypatch.setattr(constellation, "CACHE", {})

    def refuse(*args, **kwargs):
        raise urllib.error.URLError(PRIVATE_TEXT)

    monkeypatch.setattr(constellation.urllib.request, "urlopen", refuse)


def _details(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "detail":
                yield item
            else:
                yield from _details(item)
    elif isinstance(value, list):
        for item in value:
            yield from _details(item)


def _assert_names_failure_class_only(payload):
    text = json.dumps(payload, sort_keys=True)
    assert "SENTINEL-0d9e" not in text, text
    assert "/srv/upstream" not in text, text
    details = list(_details(payload))
    assert details, "a failed upstream call must still say why the value is unavailable"
    assert all(isinstance(d, str) and d.endswith("URLError") for d in details), details


@pytest.mark.parametrize(
    ("path", "state"),
    [
        ("/api/estates", "PARTIAL"),
        ("/api/kernels", "UNAVAILABLE"),
        ("/api/families/khipu/line", "UNAVAILABLE"),
    ],
)
def test_live_routes_report_state_and_failure_class_only(path, state):
    with TestClient(constellation.app) as client:
        response = client.get(path)
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == state
    _assert_names_failure_class_only(body)


@pytest.mark.parametrize("vid", PROBED_VERTICALS)
def test_endpoint_probes_report_failure_class_only(vid):
    with TestClient(constellation.app) as client:
        response = client.get(f"/api/verticals/{vid}/status")
    assert response.status_code == 200
    endpoints = response.json()["endpoints"]
    assert endpoints and all(row["state"] == "UNAVAILABLE" for row in endpoints)
    _assert_names_failure_class_only(endpoints)


@pytest.mark.parametrize(
    ("handler", "state"),
    [
        ("kernel_line", "UNAVAILABLE"),
        ("khipu_line", "UNAVAILABLE"),
        ("second_brain", "PARTIAL"),
        ("killinchu_osint", "UNAVAILABLE"),
    ],
)
def test_console_handlers_report_state_and_failure_class_only(handler, state):
    payload = getattr(constellation, handler)()
    assert payload["state"] == state
    _assert_names_failure_class_only(payload)


def test_probed_verticals_exist():
    assert PROBED_VERTICALS, "verticals.json declares no live endpoints to probe"
