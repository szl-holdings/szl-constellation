"""A posted receipt chain that does not parse is reported without exception text.

verify_receipt_chain() and receipt_curve() parse text the caller supplied; they
are served on GET /api/receipts/curve and three console buttons. A JSON syntax
error must still tell the caller where their own text is broken. Every other
parse failure is reported by class name only, because its text can describe
the server rather than the input (Python 3.14 reports the C stack size it used
for a too-deep document). CWE-209, CodeQL py/stack-trace-exposure.
"""
import json
import os

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import pytest
from fastapi.testclient import TestClient

import app as constellation

MALFORMED_JSON = [
    pytest.param("", id="empty"),
    pytest.param("[", id="open-array"),
    pytest.param('[{"prev_hash": "0"', id="truncated-receipt"),
    pytest.param('{"a": 1,}', id="trailing-comma"),
    pytest.param("[1]\n\n  x", id="extra-data-line-3"),
    pytest.param('"\\x"', id="invalid-escape"),
]


def _decoder_error(text):
    with pytest.raises(json.JSONDecodeError) as caught:
        json.loads(text)
    return f"parse error: {caught.value}"


@pytest.mark.parametrize("text", MALFORMED_JSON)
def test_json_syntax_errors_still_locate_the_fault_in_the_callers_text(text):
    expected = _decoder_error(text)
    assert constellation.verify_receipt_chain(text) == {"state": "INVALID", "detail": expected}
    assert constellation.receipt_curve(text) == {"state": "INVALID", "detail": expected, "svg": ""}


def test_receipt_curve_route_reports_where_the_posted_json_breaks():
    text = '[{"prev_hash": "0"'
    with TestClient(constellation.app) as client:
        response = client.get("/api/receipts/curve", params={"chain": text})
    assert response.status_code == 200
    assert response.json() == {"state": "INVALID", "detail": _decoder_error(text), "svg": ""}


@pytest.mark.parametrize("text", ["5", "null", '"receipts"'])
def test_json_that_is_not_an_array_is_named_as_such(text):
    assert constellation.verify_receipt_chain(text) == {
        "state": "INVALID",
        "detail": "parse error: expected a JSON array of receipts",
    }
    assert constellation.receipt_curve(text) == {
        "state": "INVALID",
        "detail": "parse error: expected a non-empty JSON array of receipts",
        "svg": "",
    }


def test_an_empty_chain_cannot_be_drawn():
    assert constellation.receipt_curve("[]") == {
        "state": "INVALID",
        "detail": "parse error: expected a non-empty JSON array of receipts",
        "svg": "",
    }


@pytest.mark.parametrize(
    ("text", "failure"),
    [
        pytest.param(None, "TypeError", id="none"),
        pytest.param(7, "TypeError", id="int"),
        pytest.param("[" * 200_000, "RecursionError", id="nested-200000-deep"),
    ],
)
def test_other_parse_failures_report_the_class_name_only(text, failure):
    for payload in (constellation.verify_receipt_chain(text), constellation.receipt_curve(text)):
        assert payload["state"] == "INVALID"
        assert payload["detail"] == f"parse error: {failure}", payload["detail"]
