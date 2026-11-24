#!/usr/bin/env python3
# mapping_study.py - measured repo-to-estate mapping study (propose-only).
# v3 repair per dual-rail re-review round 2 (nonce PR64RE-2026-11-24T153822Z, Kimi R01-R06):
#  - R01: substring repo-mention extraction REMOVED. An estate repo reference
#    is ONLY (a) a URL whose exactly-parsed hostname is github.com with the
#    repository under path-root org "szl-holdings" (urlparse: lowercase,
#    trailing-dot strip; userinfo/port handled; deceptive hosts rejected), or
#    (b) a string value that is EXACTLY a plain repo path "szl-holdings/<name>"
#    (optional ".git" suffix or trailing slash). Prose substrings never count.
#  - R04: link fields (string leaves) and edges (distinct source/field/repo
#    records) are emitted and counted separately; edge_records committed.
#  - R05: fail-closed CLI: usage, missing inputs, unreadable/invalid JSON,
#    wrong top-level shapes, malformed snapshots, and unexpected internal
#    errors all exit 2 with diagnostics; no valid-looking result on failure.
#  - R03: generation.command = the exact argv of this run (concrete paths); the
#    committed raw-results artifact is the byte-identical stdout of that command.
# Stdlib only. Offline; reads estates.json, verticals.json and an org snapshot.
import json
import os
import re
import sys
from urllib.parse import urlparse

URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
REPO_PATH_ONLY_RE = re.compile(r"^szl-holdings/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


class InputError(Exception):
    pass


def _die(msg):
    sys.stderr.write("mapping_study: " + msg + "\n")
    return 2


def load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except ValueError as e:
        raise InputError("%s: invalid JSON: %s" % (path, e))
    except OSError as e:
        raise InputError("%s: unreadable: %s" % (path, e))


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
    # A link field is a string leaf that either contains an exact-host
    # github.com URL, or is EXACTLY a plain "szl-holdings/<name>" repo path.
    # Substring mentions in prose never create estate references (R01).
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
        mentions = []
        only = REPO_PATH_ONLY_RE.match(obj.strip())
        if only:
            mentions.append(_norm_repo(only.group(1)))
        if gurls or mentions:
            out.append({
                "field": path,
                "github_repos": [r for r in (_repo_from_github_path(f["path"]) for f in gurls) if r],
                "external_github_paths": [f["path"] for f in gurls if not _repo_from_github_path(f["path"])],
                "repo_mentions": mentions,
                "value_head": obj[:60],
            })
    return out


def edge_records(source, links):
    # One record per distinct (source, field, repo). github_repos and
    # repo_mentions can hold several repos per link field, so edges are
    # counted from these records, not from link fields (R04).
    recs = []
    seen = set()
    for l in links:
        for r in l["github_repos"]:
            key = (source, l["field"], r)
            if key not in seen:
                seen.add(key)
                recs.append({"source": source, "field": l["field"], "kind": "github_url", "repo": r})
        for r in l["repo_mentions"]:
            key = (source, l["field"], r)
            if key not in seen:
                seen.add(key)
                recs.append({"source": source, "field": l["field"], "kind": "repo_path", "repo": r})
    return recs


def count_entries(container, key):
    if isinstance(container, list):
        return len(container)
    if isinstance(container, dict):
        v = container.get(key)
        if isinstance(v, list):
            return len(v)
        return len(container)
    return 0


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
    try:
        estates = load(os.path.join(root, "estates.json"))
        verticals = load(os.path.join(root, "verticals.json"))
        for label, data in (("estates.json", estates), ("verticals.json", verticals)):
            if not isinstance(data, (list, dict)):
                raise InputError(label + ": top-level JSON must be an array or object")
        org_snapshot = None
        org_snapshot_file = None
        if len(sys.argv) == 3:
            if not os.path.isfile(sys.argv[2]):
                return _die("missing snapshot file: " + sys.argv[2])
            org_snapshot = _load_snapshot(sys.argv[2])
            if org_snapshot is None:
                return _die("invalid snapshot shape: need list of repo names or {repos: [...]}")
            org_snapshot_file = os.path.basename(sys.argv[2])
    except InputError as e:
        return _die(str(e))
    n_estates = count_entries(estates, "estates")
    n_verticals = count_entries(verticals, "verticals")
    est_links = link_fields(estates)
    ver_links = link_fields(verticals)
    all_links = est_links + ver_links
    edges = edge_records("estates", est_links) + edge_records("verticals", ver_links)
    edges.sort(key=lambda r: (r["source"], r["field"], r["kind"], r["repo"]))
    repos_referenced = set(r["repo"] for r in edges)
    external_github_paths = set()
    for l in all_links:
        external_github_paths.update(l["external_github_paths"] or [])
    in_org = [r for r in sorted(repos_referenced) if (org_snapshot is None or r in org_snapshot)]
    not_in_org = [r for r in sorted(repos_referenced) if (org_snapshot is not None and r not in org_snapshot)]
    result = {
        "definitions": {
            "estate_node": "one entry of estates.json (a rendered hologram estate)",
            "vertical": "one entry of verticals.json",
            "link_field": "string leaf that contains >=1 exact-host github.com URL or is EXACTLY a plain szl-holdings/<name> repo path (whole-string match; substring mentions in prose are NOT counted)",
            "edge": "explicit record (source, field, kind, repo): one distinct estate-to-repository pairing; github_repos/repo_mentions may hold several repos per link field, so edges are counted from edge_records, not from link fields",
            "visible_element": "NOT measured by this script; requires runtime instrumentation (marked UNKNOWN)",
        },
        "exclusions": ["docs dir", "datasets subtree", "receipt files"],
        "generation": {
            "command": "python " + " ".join(sys.argv),
            "org_snapshot_file": org_snapshot_file,
            "github_host_rule": "exact parsed hostname github.com only (urlparse; lowercase; trailing dot stripped; userinfo/port handled); deceptive hosts rejected",
            "mention_rule": "estate references come ONLY from exact-host github.com URL paths or whole-string plain szl-holdings/<name> values; embedded/prose substrings never count",
            "data_inputs": "estates.json and verticals.json under data_root at this commit's tree (inspect with git show HEAD:estates.json)",
        },
        "counts": {
            "estate_nodes": n_estates,
            "verticals": n_verticals,
            "estate_link_fields": len(est_links),
            "vertical_link_fields": len(ver_links),
            "estate_to_repo_edges": len(edges),
            "distinct_repos_referenced": len(repos_referenced),
            "repos_in_org_snapshot": len(in_org),
            "repos_referenced_not_in_org_snapshot": not_in_org,
            "external_github_paths": sorted(external_github_paths),
            "org_repos_at_snapshot": (len(org_snapshot) if org_snapshot is not None else None),
        },
        "edge_records": edges,
        "unknowns": ["visible element counts and interaction load are NOT asserted; runtime instrumentation required"],
    }
    print(json.dumps(result, indent=2))
    return 0


def _run():
    try:
        return main()
    except Exception as e:
        sys.stderr.write("mapping_study: internal error (no result emitted): %s: %s\n" % (type(e).__name__, e))
        return 2


if __name__ == "__main__":
    sys.exit(_run())
