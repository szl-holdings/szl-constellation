#!/usr/bin/env python3
# mapping_study.py - measured repo-to-estate mapping study (propose-only).
# Per Kimi governing ruling NEXT2-20261124T132125Z item B: measured, reproducible
# node/edge/visible counts with explicit definitions, exclusions, raw results.
# Stdlib only. Offline; reads a pre-saved org repos snapshot JSON.
import json
import os
import sys
import re
from urllib.parse import urlsplit


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def repo_reference(value):
    """Return a repo name only for an exact SZL slug or GitHub HTTPS URL."""
    if not isinstance(value, str):
        return None
    if any(ch.isspace() or ord(ch) < 32 for ch in value):
        return None
    match = re.fullmatch(r"szl-holdings/([A-Za-z0-9_.-]+)", value)
    if match:
        name = match.group(1)
    else:
        try:
            parsed = urlsplit(value)
            if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
                return None
        except ValueError:
            return None
        match = re.fullmatch(
            r"/szl-holdings/([A-Za-z0-9_.-]+)(?:/[^?#]*)?", parsed.path
        )
        if not match:
            return None
        name = match.group(1)
    return name if name not in (".", "..") else None


def link_fields(obj):
    # Only explicit SZL repository references count as edges.
    links = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if (repo := repo_reference(v)) is not None:
                links.append({"field": k, "value": v[:120], "repo": repo})
            elif isinstance(v, (list, dict)):
                links.extend(link_fields(v))
    elif isinstance(obj, list):
        for item in obj:
            links.extend(link_fields(item))
    return links


def count_entries(container, key):
    if isinstance(container, list):
        return len(container)
    if isinstance(container, dict):
        v = container.get(key)
        if isinstance(v, list):
            return len(v)
        return len(container)
    return 0


def main():
    root = sys.argv[1]
    estates = load(os.path.join(root, "estates.json"))
    verticals = load(os.path.join(root, "verticals.json"))
    n_estates = count_entries(estates, "estates")
    n_verticals = count_entries(verticals, "verticals")
    est_links = link_fields(estates)
    ver_links = link_fields(verticals)
    repos_referenced = {link["repo"] for link in est_links + ver_links}
    org_snapshot = None
    if len(sys.argv) > 2 and os.path.isfile(sys.argv[2]):
        org_snapshot = load(sys.argv[2])
    in_org = [r for r in sorted(repos_referenced) if (org_snapshot is None or r in org_snapshot)]
    not_in_org = [r for r in sorted(repos_referenced) if (org_snapshot is not None and r not in org_snapshot)]
    result = {
        "definitions": {
            "estate_node": "one entry of estates.json (a rendered hologram estate)",
            "vertical": "one entry of verticals.json",
            "edge": "exact szl-holdings repo slug or HTTPS github.com URL with a szl-holdings repository path",
            "visible_element": "NOT measured by this script; requires runtime instrumentation (marked UNKNOWN)",
        },
        "exclusions": ["docs dir", "datasets subtree", "receipt files"],
        "counts": {
            "estate_nodes": n_estates,
            "verticals": n_verticals,
            "estate_link_fields": len(est_links),
            "vertical_link_fields": len(ver_links),
            "distinct_repos_referenced": len(repos_referenced),
            "repos_in_org_snapshot": len(in_org),
            "repos_referenced_not_in_org_snapshot": not_in_org,
            "org_repos_at_snapshot": (len(org_snapshot) if org_snapshot else None),
        },
        "unknowns": ["visible element counts and interaction load are NOT asserted; runtime instrumentation required"],
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
