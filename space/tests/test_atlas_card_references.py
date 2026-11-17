"""Public Hub Space-card reference contracts: precise edges, no inferred authority."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import atlas_public as atlas

STAMP = datetime(2026, 11, 17, 9, 40, tzinfo=timezone.utc)
A = "a" * 40


def entry(short, *, private=False, sha=A, **fields):
    return SimpleNamespace(
        id="SZLHOLDINGS/" + short, private=private, sha=sha,
        last_modified=STAMP, tags=["license:apache-2.0"], **fields
    )


@pytest.fixture
def sample(tmp_path):
    topology = tmp_path / "verticals.json"
    topology.write_text(json.dumps({
        "generated": "2026-09-04T00:00:00Z",
        "verticals": [{
            "id": "killinchu", "name": "Killinchu",
            "spaces": ["SZLHOLDINGS/killinchu"], "models": [],
            "datasets": [],
        }],
    }), encoding="utf-8")
    assets = {
        "space": [entry("killinchu", models=[
            "SZLHOLDINGS/Khipu", "SZLHOLDINGS/Khipu",
            "SZLHOLDINGS/SECRET_MODEL", "thirdparty/model-v3",
        ], datasets=["SZLHOLDINGS/PublicData", "SZLHOLDINGS/PRIVATE_DATA"])],
        "model": [entry("Khipu"), entry("SECRET_MODEL", private=True)],
        "dataset": [entry("PublicData"), entry("PRIVATE_DATA", private=True)],
    }
    return topology, assets


def observe(sample):
    topology, assets = sample
    return atlas.collect(
        lister=lambda kind, limit: assets[kind],
        topology_path=topology, now=STAMP
    )


def test_exact_public_card_references_have_distinct_provenance(sample):
    report = observe(sample)
    cards = [edge for edge in report["links"]
             if edge["kind"].startswith("PUBLIC_SPACE_CARD_")]
    assert report["card_link_count"] == 2
    assert report["card_link_evidence"] == "PUBLIC_SPACE_CARD_REFERENCE_NOT_RUNTIME_DEPENDENCY"
    assert len(cards) == 2
    assert {e["target"] for e in cards} == {
        "model:SZLHOLDINGS/Khipu", "dataset:SZLHOLDINGS/PublicData"
    }
    assert all(e["source"] == "space:SZLHOLDINGS/killinchu" for e in cards)
    assert all(e["source_revision"] == A for e in cards)
    assert all(e["evidence_state"] == "CARD_DECLARATION_NOT_EXECUTED_DEPENDENCY"
               for e in cards)
    assert all(e["kind"] in (
        "PUBLIC_SPACE_CARD_REFERENCES_MODEL",
        "PUBLIC_SPACE_CARD_REFERENCES_DATASET",
    ) for e in cards)
    # Secondary card references NEVER modify dated vertical membership.
    khipu = next(n for n in report["nodes"] if n["id"] == "model:SZLHOLDINGS/Khipu")
    assert khipu["verticals"] == []
    assert report["production_qualified"] is False
    assert report["execution_authorized"] is False


def test_private_and_external_references_never_escape(sample):
    report = observe(sample)
    text = json.dumps(report)
    for forbidden in ("SECRET_MODEL", "PRIVATE_DATA", "thirdparty/model-v3"):
        assert forbidden not in text
    assert report["counts"] == {"space": 1, "model": 1, "dataset": 1}
    assert len(report["links"]) == 3  # One historical edge + two card edges.


def test_private_space_cannot_emit_links(sample):
    topology, rows = sample
    rows["space"][0].private = True
    report = observe(sample)
    assert report["card_link_count"] == 0
    assert not any(e["kind"].startswith("PUBLIC_SPACE_CARD") for e in report["links"])


def test_card_with_missing_source_sha_cannot_make_bound_edge(sample):
    _, rows = sample
    rows["space"][0].sha = None
    report = observe(sample)
    assert report["card_link_count"] == 0
    assert not any(e["kind"].startswith("PUBLIC_SPACE_CARD") for e in report["links"])


@pytest.mark.parametrize("bad", ["SZLHOLDINGS/Khipu", {"SZLHOLDINGS/Khipu"}, 16])
def test_non_list_card_reference_contract_fails_closed(sample, bad):
    _, rows = sample
    rows["space"][0].models = bad
    with pytest.raises(atlas.AtlasError, match="PUBLIC_SPACE_CARD_RELATION_SET_INVALID"):
        observe(sample)


def test_oversized_card_reference_set_fails_closed(sample):
    _, rows = sample
    rows["space"][0].datasets = ["SZLHOLDINGS/PublicData"] * (
        atlas.MAX_CARD_REFERENCES_PER_KIND + 1
    )
    with pytest.raises(atlas.AtlasError, match="PUBLIC_SPACE_CARD_RELATION_SET_INVALID"):
        observe(sample)


def test_invalid_card_reference_type_fails_closed(sample):
    _, rows = sample
    rows["space"][0].models = [None]
    with pytest.raises(atlas.AtlasError, match="PUBLIC_SPACE_CARD_RELATION_TYPE_INVALID"):
        observe(sample)


def test_response_digest_changes_when_card_declarations_change(sample):
    first = observe(sample)
    sample[1]["space"][0].models = []
    second = observe(sample)
    assert first["observation_sha256"] != second["observation_sha256"]
    assert first["card_link_count"] != second["card_link_count"]


def test_default_hub_reader_requests_anonymous_linked_space_metadata(sample):
    topology, rows = sample
    class FakeHub:
        seen = []
        def __init__(self, token):
            assert token is False
        def list_spaces(self, **kwargs):
            self.seen.append(("space", kwargs))
            return rows["space"]
        def list_models(self, **kwargs):
            self.seen.append(("model", kwargs))
            return rows["model"]
        def list_datasets(self, **kwargs):
            self.seen.append(("dataset", kwargs))
            return rows["dataset"]
    with patch("huggingface_hub.HfApi", FakeHub):
        report = atlas.collect(topology_path=topology, now=STAMP)
    assert report["card_link_count"] == 2
    assert len(FakeHub.seen) == 3
    for kind, kwargs in FakeHub.seen:
        assert kwargs["author"] == "SZLHOLDINGS"
        assert kwargs["token"] is False
        assert kwargs["full"] is True
        if kind == "space":
            assert kwargs["linked"] is True
        else:
            assert "linked" not in kwargs


def test_card_reference_target_nonpublic_after_listing_remains_absent(sample):
    _, rows = sample
    rows["model"] = []
    report = observe(sample)
    assert not any(e["target"] == "model:SZLHOLDINGS/Khipu" for e in report["links"])
    assert report["card_link_count"] == 1

def test_public_graph_cap_matches_client_limit(sample):
    with patch.object(atlas, "MAX_PUBLIC_GRAPH_LINKS", 1):
        with pytest.raises(atlas.AtlasError, match="PUBLIC_GRAPH_LINK_LIMIT_EXCEEDED"):
            observe(sample)
