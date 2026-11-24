#!/usr/bin/env python3
# mapping_study.py - measured repo-to-estate mapping study (propose-only).
# v2 repair per dual-rail re-review (UNIFY-GOV-2026-11-24T143612Z, PR64 F01-F04):
#  - github.com accepted ONLY as an exact parsed hostname (urlparse, lowercase,
#    trailing-dot strip); szl-holdings matched in the parsed URL path, never via
#    raw substring heuristics (clears the CodeQL URL-sanitization alert).
#  - parse BEFORE truncation: repo names are extracted from full values; the
#    120-char display truncation no longer gates extraction.
#  - .git suffix and #/?/& terminators normalized; org must be szl-holdings path-root.
#  - fail-closed CLI: explicit usage/missing-input/invalid-snapshot errors, exit 2.
# Stdlib only. Offline; reads estates.json, verticals.json and an org snapshot.
import json
import os
import re
import sys
from urllib.parse import urlparse

URL_RE = re.compile(r"https?://[^\s\"\x27<>]+", re.IGNORECASE)
REPO_PATH_RE = re.compile(r"(?<![A-Za-z0-9_./-])szl-holdings/([A-Za-z0-9_.-]+)")


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _norm_repo(name):
    name = name.strip()
    if name.endswith(".git"):
        name = name[:-4]
    return name


def _github_facts(url):
    try:
        p = urlparse(url)
    except Exception:
        return None
    host = (p.hostname or "").lower().rstrip(".")
    return {"url": url, "host": host, "path": p.path or ""}


def _repo_from_github_path(path):
    parts = [s for s in path.split("/") if s]
    if len(parts) >= 2 and parts[0].lower() == "szl-holdings":
        return _norm_repo(parts[1])
    return None


def link_fields(obj, path=""):
    # A link field is a string leaf that either contains an exact-host github.com
    # URL, or contains an szl-holdings/<name> repo-path mention. Deceptive hosts
    # (e.g. github.com.evil.io) are rejected by exact-host comparison.
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(link_fields(v, path + "/" + str(k)))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            out.extend(link_fields(item, path + "/%d" % i))
    elif isinstance(obj, str):
        gurls = []
        for m in URL_RE.finditer(obj):
            f = _github_facts(m.group(0))
            if f and f["host"] == "github.com":
                gurls.append(f)
        mentions = [_norm_repo(m.group(1)) for m in REPO_PATH_RE.finditer(obj)]
        if gurls or mentions:
            out.append({
                "field": path,
                "github_repos": [r for r in (_repo_from_github_path(f["path"]) for f in gurls) if r],
                "external_github_paths": [f["path"] for f in gurls if not _repo_from_github_path(f["path"])],
                "repo_mentions": mentions,
                "value_head": obj[:60],
            })
    return out


def count_entries(container, key):
    if isinstance(container, list):
        return len(container)
    if isinstance(container, dict):
        v = container.get(key)
        if isinstance(v, list):
            return len(v)
        return len(container)
    return 0


def _die(msg):
    sys.stderr.write("mapping_study: " + msg + "\n")
    return 2


def _load_snapshot(path):
    data = load(path)
    if isinstance(data, list) and all(isinstance(x, str) for x in data):
        return set(data)
    if isinstance(data, dict):
        v = data.get("repos")
        if isinstance(v, list) and all(isinstance(x, str) for x in v):
            return set(v)
    return None


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        return _die("usage: mapping_study.py <data_root> [org_snapshot.json]")
    root = sys.argv[1]
    for name in ("estates.json", "verticals.json"):
        if not os.path.isfile(os.path.join(root, name)):
            return _die("missing input: " + os.path.join(root, name))
    estates = load(os.path.join(root, "estates.json"))
    verticals = load(os.path.join(root, "verticals.json"))
    org_snapshot = None
    org_snapshot_file = None
    if len(sys.argv) == 3:
        if not os.path.isfile(sys.argv[2]):
            return _die("missing snapshot file: " + sys.argv[2])
        org_snapshot = _load_snapshot(sys.argv[2])
        if org_snapshot is None:
            return _die("invalid snapshot shape: need list of repo names or {repos: [...]}",
                        )
        org_snapshot_file = os.path.basename(sys.argv[2])
    n_estates = count_entries(estates, "estates")
    n_verticals = count_entries(verticals, "verticals")
    est_links = link_fields(estates)
    ver_links = link_fields(verticals)
    all_links = est_links + ver_links
    repos_referenced = set()
    external_github_paths = set()
    for l in all_links:
        repos_referenced.update(l["github_repos"])
        repos_referenced.update(l["repo_mentions"])
        external_github_paths.update(l["external_github_paths"] or [])
    in_org = [r for r in sorted(repos_referenced) if (org_snapshot is None or r in org_snapshot)]
    not_in_org = [r for r in sorted(repos_referenced) if (org_snapshot is not None and r not in org_snapshot)]
    result = {
        "definitions": {
            "estate_node": "one entry of estates.json (a rendered hologram estate)",
            "vertical": "one entry of verticals.json",
            "edge": "string leaf containing an exact-host github.com URL or an szl-holdings/<name> repo-path mention (v2: parsed, not substring-matched)",
            "visible_element": "NOT measured by this script; requires runtime instrumentation (marked UNKNOWN)",
        },
        "exclusions": ["docs dir", "datasets subtree", "receipt files"],
        "generation": {
            "command": "python tools/mapping_study.py <data_root> <org_snapshot.json>",
            "org_snapshot_file": org_snapshot_file,
            "github_host_rule": "exact parsed hostname github.com only; deceptive hosts rejected",
        },
        "counts": {
            "estate_nodes": n_estates,
            "verticals": n_verticals,
            "estate_link_fields": len(est_links),
            "vertical_link_fields": len(ver_links),
            "distinct_repos_referenced": len(repos_referenced),
            "repos_in_org_snapshot": len(in_org),
            "repos_referenced_not_in_org_snapshot": not_in_org,
            "external_github_paths": sorted(external_github_paths)[:20],
            "org_repos_at_snapshot": (len(org_snapshot) if org_snapshot is not None else None),
        },
        "unknowns": ["visible element counts and interaction load are NOT asserted; runtime instrumentation required"],
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
