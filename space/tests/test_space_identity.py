"""The runtime reports the Space it actually runs on, from an allowlist of two."""
import os

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import pytest

import app as constellation


@pytest.mark.parametrize(
    "declared,expected",
    [
        ("SZLHOLDINGS/szl-constellation", "SZLHOLDINGS/szl-constellation"),
        ("SZLHOLDINGS/szl-constellation-staging", "SZLHOLDINGS/szl-constellation-staging"),
        (" SZLHOLDINGS/szl-constellation-staging ", "SZLHOLDINGS/szl-constellation-staging"),
        ("", "SZLHOLDINGS/szl-constellation"),
        ("SZLHOLDINGS/other", "SZLHOLDINGS/szl-constellation"),
        ("szlholdings/szl-constellation-staging", "SZLHOLDINGS/szl-constellation"),
    ],
)
def test_space_id_is_allowlisted(declared, expected):
    assert constellation._resolve_space_id(declared) == expected


def test_each_known_space_has_its_own_host():
    hosts = constellation.KNOWN_SPACE_HOSTS
    assert hosts["SZLHOLDINGS/szl-constellation"] == "szlholdings-szl-constellation.hf.space"
    assert hosts["SZLHOLDINGS/szl-constellation-staging"] == "szlholdings-szl-constellation-staging.hf.space"
    assert constellation.SPACE_HOST == hosts[constellation.SPACE_ID]


def test_provider_runtime_checks_the_resolved_host(monkeypatch):
    import io
    import json

    monkeypatch.setattr(constellation, "SPACE_ID", "SZLHOLDINGS/szl-constellation-staging")
    monkeypatch.setattr(constellation, "SPACE_HOST", "szlholdings-szl-constellation-staging.hf.space")
    seen = []

    def upstream(request, timeout):
        seen.append(request.full_url)
        body = io.BytesIO(json.dumps({"runtime": {
            "stage": "RUNNING",
            "sha": "a" * 40,
            "replicas": {"current": 1},
            "domains": [{"domain": "szlholdings-szl-constellation.hf.space", "stage": "READY"}],
        }}).encode())
        body.headers = {"Content-Type": "application/json"}
        return body

    monkeypatch.setattr(constellation.urllib.request, "urlopen", upstream)
    with pytest.raises(ValueError, match="one ready replica"):
        constellation._provider_runtime()
    assert seen == ["https://huggingface.co/api/spaces/SZLHOLDINGS/szl-constellation-staging"]
