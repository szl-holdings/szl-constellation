# Public Frontier Atlas — source-to-Hub visualization architecture
Observed 2026-11-17. A read-only feature added to the canonical szl-constellation
repository, not an authority or a new publisher.

## Reference systems studied
| System | Relevant affordance | SZL implementation choice | Copyright/license boundary |
|---|---|---|---|
| [Palantir Object Explorer](https://www.palantir.com/docs/foundry/object-explorer/overview) and [Ontology](https://www.palantir.com/docs/foundry/ontology) | object groups, typed links, object-specific inspection | exact public Hub IDs, dated explicit vertical links, selected-entity inspector | product design concepts only; no Palantir code |
| [Palantir Vertex](https://www.palantir.com/docs/foundry/getting-started/application-reference) | visualize systems and relationship graphs | typed edges only when current public Hub metadata matches declared vertical references | no private ontologies or proprietary APIs |
| [NVIDIA OpenUSD / Omniverse](https://github.com/NVIDIA-Omniverse/omniverse-kit) | 3D scene graphs, digital twin imagery, semantic simulation geometry | WebGL observational graph, *not* a simulation or physically accurate digital twin | OV Libraries preview/license reviewed; not bundled |
| [3d-force-graph](https://github.com/vasturiano/3d-force-graph) | interactive 3D force networks, raycasting, zooming | deterministic 3D layouts, node picking, zoom/orbit; avoid graph force implying causality | MIT reference only, no code copied |
| [Cytoscape.js](https://js.cytoscape.org/) | large scientific networks and accessible graph exploration | typed node/edge schema and searchable flat directory fallback | MIT reference only |
| [Graphology](https://github.com/graphology/graphology) | explicit graph model vs presentation separation | Python schema emits typed references; presentation does not infer new edges | MIT reference only |
| [Three.js](https://github.com/mrdoob/three.js) | vendorable GPU-efficient WebGL and camera controls | Three.js 0.187.0, InstancedMesh, OrbitControls, Raycaster, bounded pixel ratio | MIT; vendored with exact SHA-256 pins and included license |

## Exact source and data boundary
- **Canonical code**: GitHub szl-holdings/szl-constellation.
- **Public metadata**: anonymous Hugging Face Hub API, `author=SZLHOLDINGS`,
  `token=False`, exact org identity, `private is False` filter. No
  authenticated owner inventory is mixed into the public response. A separate
  local inventory can contain nonpublic counts but is never served here.
- **Vertical topology**: `space/verticals.json`, generated Sept 2026 and
  explicitly marked HISTORICAL_DECLARED_RELATIONSHIPS. A link is drawn only
  when a referenced asset exists in the fresh anonymous public list. No
  heuristic entity matching, guessed causal edges or synthetic readyness.
- **Cardinality**: 2026-11-17 anonymous read saw 31 public Spaces, 147 public
  models, 91 public datasets, and 8 dated verticals. A logged-in owner read
  saw one additional public-marked Space; the public site uses anonymous
  discovery rather than assuming that owner-visible data is universally
  discoverable. These values are observations, not persistent constants.
- **Freshness**: Python producer is cached for 300 seconds with one producer
  per process; a failed refresh returns 503 and never reuses an expired
  observation. The browser does not invent a fallback graph.
- **Honesty states**: observed public *metadata* and dated *declared topology*
  do not establish Space readiness, artifact quality, model training status,
  receipt signatures, production release admission, clinical validation,
  financial returns, deployment authority or payment settlement.
- **Safety**: metadata GETs only, no dataset rows, model weights, restricted
  endpoints, provider mutations, payment, training jobs, medical records,
  government secrets or private project names. All user-controlled text
  goes through textContent. Links are constructed from allow-listed IDs.
- **Routes**: `/atlas/` is an additive self-hosted viewer. Public
  `/api/atlas/public` serves the bounded schema. `?space=SZLHOLDINGS/...`
  and `?vertical=killinchu` create reproducible interactive lenses.
  Each of the listed public Spaces is selectable independently without
  modifying or overriding its native Space.
- **Reproduction**: `python -m pytest -q space/tests/test_atlas_public.py`
  (run from `space/`), render via `tools/verify_atlas_browser.py` in the
  existing Playwright CI environment. Browser fixtures are marked synthetic
  and do not represent live providers.

## Live public Space-card reference graph (2026-11-17 extension)

The atlas now distinguishes TWO entirely separate provenance classes:

1. `DECLARED_MEMBERSHIP_MATCHED_TO_PUBLIC_HUB`: source-listed
   September 2026 vertical membership matched to an anonymously listed public
   Hub resource. This is **not a currently qualified vertical runtime**.
2. `PUBLIC_SPACE_CARD_REFERENCES_MODEL` /
   `PUBLIC_SPACE_CARD_REFERENCES_DATASET`: explicit model/dataset IDs
   published in the anonymous public Space card, matched independently
   against the public model or dataset census. The link includes the Space's
   exact Hub source SHA and is labeled
   `CARD_DECLARATION_NOT_EXECUTED_DEPENDENCY`. It does not establish that
   a model was loaded, that dataset rows were used, that training happened,
   or that either asset belongs to a historical vertical.

Source collection calls `HfApi(token=False).list_spaces(author="SZLHOLDINGS",
full=True,linked=True,token=False)` plus independently scoped anonymous
model/dataset lists. A card references an asset only if the exact same-org
ID is present and independently public; external, nonpublic, malformed and
ambiguous IDs are never disclosed or relabeled.

The browser renders dated vertical edges as SOLID cyan and public card
references as DASHED lilac. The evidence inspector lets the user follow
exact matched Space-card references. The optional "Include public
Space-card references" vertical lens reveals *indirectly connected*
assets without changing their dated membership. The directory explicitly
calls such rows "Via public Space card — NOT vertical membership".
All links remain read-only and neither type establishes action authority.

First source probe in this campaign: 33 anonymously listed public Spaces,
147 public models, 93 public datasets, and **36** independent exact public
Space-card links (20 model, 16 dataset) at
2026-11-17 ~09:45 UTC. Counts are observations, not constants.

Verification: the Python suite covers malformed card metadata, duplicate
references, foreign references, nonpublic resources, oversize lists,
missing source SHA, no extra vertical memberships, and digest changes.
Chromium tests render both edge styles, toggle the indirect vertical
lens, traverse a source-linked model from a Space inspector, and reject
a forged source SHA without rendering fake evidence.

External references: Hugging Face Hub `list_spaces(linked=True)`
documentation and Space Card metadata guide. No open-source code copied
to produce the edge semantics: the Python and JS graph projection is
original SZL implementation using existing vendored, MIT-licensed Three.js.
