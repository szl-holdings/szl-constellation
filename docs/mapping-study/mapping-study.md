# Repo-to-estate mapping study (propose-only)

Governing ruling: Kimi NEXT2-20261124T132125Z item B (BUILD_PROPOSE_ONLY); satisfies
the CONSTK1 scale-claim edit: repo count is NOT a renderable node count; the mapping
must be defined and measured before any scale claim or benchmark.

## Definitions
- estate node: one entry of estates.json (a rendered hologram estate)
- vertical: one entry of verticals.json
- edge: explicit string link to a szl-holdings repo (field mentioning szl-holdings/
  or github.com)
- visible element: NOT measured here; requires runtime instrumentation (UNKNOWN)

## Method (reproducible)
1. tools/mapping_study.py (stdlib-only, committed with this PR) parses estates.json
   and verticals.json and counts nodes, link fields, and distinct referenced repos.
2. Org repo list snapshot taken fresh via gh api at measurement time (snapshot JSON
   committed; STAMP in filename).
3. Exclusions: docs dir, datasets subtree, receipt files. No runtime instrumentation.

## Raw results
See raw-results-<stamp>.json for the machine-readable output with definitions,
exclusions, counts, referenced repo names, and UNKNOWNs. Summary printed in the PR
conversation at creation time.

## Honesty rules
No scale, performance, or coverage claims beyond the measured counts. Visible
elements and interaction load remain UNKNOWN until runtime instrumentation exists.
Re-measure with the committed tool at any later revision before quoting numbers.
