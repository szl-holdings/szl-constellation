# SPDX-License-Identifier: Apache-2.0
"""Exercise urllib's redirect machinery without opening a network socket."""

from __future__ import annotations

import io
import socket
import urllib.request
import urllib.response
from email.message import Message

import pytest

import publish_constellation as publisher

HUB = "https://huggingface.co"
STAGING = "https://szlholdings-szl-constellation-staging.hf.space"
TOKEN = "offline-private-token"


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("transport test attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


class RecordingHTTPS(urllib.request.BaseHandler):
    handler_order = 100

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def https_open(self, request):
        self.requests.append((request.full_url, request.get_header("Authorization")))
        status, location, body = self.routes[request.full_url]
        headers = Message()
        headers["Content-Type"] = "application/json"
        if location is not None:
            headers["Location"] = location
        response = urllib.response.addinfourl(io.BytesIO(body), headers, request.full_url, status)
        response.msg = "Found" if location else "OK"
        return response


@pytest.fixture
def transport(monkeypatch):
    build_opener = urllib.request.build_opener

    def install(routes):
        fake = RecordingHTTPS(routes)
        monkeypatch.setattr(
            publisher.urllib.request,
            "build_opener",
            lambda handler: build_opener(handler, fake),
        )
        return fake, build_opener(fake)

    return install


@pytest.mark.parametrize("origin", [HUB, STAGING])
def test_private_requests_use_the_bearer_at_the_two_closed_origins(transport, origin):
    fake, _ = transport({origin + "/source": (200, None, b"{}")})
    assert publisher.request_bytes(origin + "/source", token=TOKEN) == (
        200, "application/json", b"{}"
    )
    assert fake.requests == [(origin + "/source", "Bearer " + TOKEN)]


@pytest.mark.parametrize("origin", [HUB, STAGING])
def test_same_origin_relative_redirect_preserves_private_readback(transport, origin):
    fake, _ = transport({
        origin + "/source": (302, "/resolved", b"redirect"),
        origin + "/resolved": (200, None, b"source bytes"),
    })
    assert publisher.request_bytes(origin + "/source", token=TOKEN)[2] == b"source bytes"
    assert fake.requests == [
        (origin + "/source", "Bearer " + TOKEN),
        (origin + "/resolved", "Bearer " + TOKEN),
    ]


@pytest.mark.parametrize("destination", [
    "https://example.invalid/steal",
    "http://huggingface.co/steal",
    "https://huggingface.co:444/steal",
    STAGING + "/steal",
])
def test_private_redirect_refused_before_a_second_request(transport, destination):
    fake, _ = transport({HUB + "/source": (302, destination, b"redirect")})
    with pytest.raises(RuntimeError, match="credential"):
        publisher.request_bytes(HUB + "/source", token=TOKEN)
    assert fake.requests == [(HUB + "/source", "Bearer " + TOKEN)]


@pytest.mark.parametrize("url", [
    "https://example.invalid/source",
    "http://huggingface.co/source",
    "https://huggingface.co:444/source",
    "https://huggingface.co:not-a-port/source",
    "https://user@huggingface.co/source",
    "https://user:password@huggingface.co/source",
    "https://huggingface.co@example.invalid/source",
    "https://szlholdings-szl-constellation.hf.space/source",
])
def test_initial_credential_origin_refused_before_transport(monkeypatch, url):
    def denied(*args, **kwargs):
        pytest.fail("invalid initial origin reached the transport")

    monkeypatch.setattr(publisher.urllib.request, "build_opener", denied)
    monkeypatch.setattr(publisher.urllib.request, "urlopen", denied)
    with pytest.raises(RuntimeError, match="credential"):
        publisher.request_bytes(url, token=TOKEN)


def test_anonymous_cross_origin_redirect_keeps_existing_behavior(transport, monkeypatch):
    fake, anonymous = transport({
        HUB + "/source": (302, "https://example.invalid/public", b"redirect"),
        "https://example.invalid/public": (200, None, b"public bytes"),
    })
    monkeypatch.setattr(publisher.urllib.request, "urlopen", anonymous.open)
    assert publisher.request_bytes(HUB + "/source")[2] == b"public bytes"
    assert fake.requests == [(HUB + "/source", None), ("https://example.invalid/public", None)]
