# Repo-to-estate mapping study (propose-only)

Governing ruling: Kimi NEXT2-20261124T132125Z item B (BUILD_PROPOSE_ONLY); satisfies
the CONSTK1 scale-claim edit: repo count is NOT a renderable node count; the mapping
must be defined and measured before any scale claim or benchmark.

## Definitions
- estate node: one entry of estates.json (a rendered hologram estate)
- vertical: one entry of verticals.json
- link field: string leaf that contains >=1 exact-host github.com URL or is EXACTLY
  a plain szl-holdings/<name> repo path (whole-string match; prose substrings do
  not count)
- edge: explicit estate-to-repository pairing (source, field, kind, repo) extracted
  only from exact-host github.com URL paths or whole-string szl-holdings/<name>
  values; counted from edge_records, not from link fields (v3)
- visible element: NOT measured here; requires runtime instrumentation (UNKNOWN)

## Method (reproducible)
1. tools/mapping_study.py (stdlib-only, committed with this PR) parses estates.json
   and verticals.json and counts nodes, link fields, edges, and distinct repos.
2. Org repo list snapshot taken fresh via gh api at measurement time (snapshot JSON
   committed; STAMP in filename).
3. Exclusions: docs dir, datasets subtree, receipt files. No runtime instrumentation.

## Raw results
See raw-results-<stamp>.json for the machine-readable output with definitions,
exclusions, counts, edge records, and UNKNOWNs. The reproducible artifact is the
latest stamped file (v3, see the v3 addendum below).

## Honesty rules
No scale, performance, or coverage claims beyond the measured counts. Visible
elements and interaction load remain UNKNOWN until runtime instrumentation exists.
Re-measure with the committed tool at any later revision before quoting numbers.

## v2 repair (re-review F01-F04)

- Tool repaired: exact-host URL parsing (github.com hostname only, urllib.parse), szl-holdings
  matched in parsed URL paths, parse-before-truncation, .git normalization, fail-closed CLI.
- Regression battery: tools/tests/test_mapping_study.py (nested, dict-shaped, deceptive hosts,
  pseudo-extension hosts, parse-before-truncation, multi-link, CLI error classes).
- Generation command (verbatim artifact raw-results-2026-11-24T151209Z.json):
  python tools/mapping_study.py <data_root> docs/mapping-study/org-repos-snapshot-20261124T132311Z.json
  where <data_root> is the repo directory containing estates.json and verticals.json.
- The prior v1 raw-results file predates the v2 repair and is kept for history.

## v3 repair (re-review round 2, nonce PR64RE-2026-11-24T153822Z, Kimi findings R01-R06)

- R01: substring repo-mention extraction REMOVED. An estate repo reference is ONLY
  (a) a URL whose exactly-parsed hostname is github.com with the repository under
  path-root org szl-holdings, or (b) a string value that is EXACTLY a plain
  szl-holdings/<name> repo path (optional .git suffix or trailing slash). Prose
  substrings, deceptive hosts, and embedded refs never count.
- R02: regression battery expanded to 32 tests, all green locally: deceptive URL as
  the only value (end-to-end CLI: zero refs, zero edges, deceptive host absent from
  output), bare szl-holdings.github.com, userinfo/port/trailing-dot host variants,
  external-org URLs, prose substring non-counting, whole-string repo paths, edge
  record semantics and dedupe, CLI fail-closed classes, aggregate CLI assertions.
- R03 reproducibility: exact command, executed from the repo root:
  python -X utf8 tools/mapping_study.py . docs/mapping-study/org-repos-snapshot-20261124T132311Z.json > docs/mapping-study/raw-results-2026-11-24T154708Z.json
  The committed raw-results-2026-11-24T154708Z.json is the byte-identical stdout of
  that command; regenerated a second time and byte-compared identical (fc /b: no
  differences). The artifact's generation.command field records the argv form
  (python tools/mapping_study.py . docs/mapping-study/org-repos-snapshot-20261124T132311Z.json).
- R04: link fields and edges are separate measurements: link fields count string
  leaves; edges are explicit (source, field, kind, repo) records in edge_records.
- R05: fail-closed CLI extended: invalid JSON, unreadable files, wrong top-level
  shapes, and unexpected internal errors all exit 2 with diagnostics and emit no
  seemingly-valid result (previously some of these crashed with a traceback).
- v3 corrected measurement, from the repo-root estates.json/verticals.json at this
  commit: 49 estate nodes, 8 verticals, 27 estate link fields, 38 vertical link
  fields, 65 estate-to-repo edges, 49 distinct repos referenced, all 49 present in
  the 191-repo org snapshot, 0 dangling references, 0 external github.com paths.
  Visible elements remain UNKNOWN (no runtime instrumentation).
- R06 note: the numeric claims above are produced by the committed tool from the
  committed inputs (estates.json, verticals.json, org snapshot) at this commit;
  reviewers can re-run the exact command above to re-derive the artifact bytes.
- Prior raw-results files (v1 raw-results-20261124T132311Z.json, v2
  raw-results-2026-11-24T151209Z.json) are kept for history; the v3 file named
  above is the reproducible artifact.
