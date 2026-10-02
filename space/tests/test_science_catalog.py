"""Published science assets and source candidates remain distinct in the public map."""

import json
from pathlib import Path


SPACE = Path(__file__).resolve().parents[1]


def test_science_catalog_card_has_exact_release_and_candidate_boundaries():
    manifest = json.loads((SPACE / "estates.json").read_text(encoding="utf-8"))
    cards = [entry for entry in manifest["estates"] if entry["name"] == "szl-skills"]
    assert len(cards) == 1

    card = cards[0]
    assert card["repo"] == "szl-holdings/szl-skills"
    assert card["private"] is False
    assert card["hub_relation"] == "CURATED_PORTFOLIO_GROUPING"
    assert card.get("live", []) == []
    assert card["release"] == {
        "tag": "v0.5.0-rc.1",
        "source_revision": "0bbc3e2182c6512edeaf1641fcfa6dd8fb410610",
        "url": "https://github.com/szl-holdings/szl-skills/releases/tag/v0.5.0-rc.1",
    }
    assert card["candidate"] == {
        "number": 38,
        "url": "https://github.com/szl-holdings/szl-skills/pull/38",
        "scope": "SYNTHETIC_ONLY_NOT_IN_RELEASE",
    }
    assert "not a deployed clinical system" in card["desc"]
    assert "outside this release" in card["desc"]


def test_science_release_and_candidate_are_not_labeled_live_in_panel():
    source = (SPACE / "holo" / "index.html").read_text(encoding="utf-8")
    assert "published ZIPs · ${e.release.tag}" in source
    assert "immutable release source" in source
    assert "source candidate · PR #${e.candidate.number} (outside release)" in source
    assert "ZIP assets, not a running service" in source
    assert "files at release source" in source
    assert "Catalogued with" in source
