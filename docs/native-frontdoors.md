# Native Constellation front doors

This change updates the four interfaces actually served by `space/app.py`:

| Route | Presentation source | Scope |
| --- | --- | --- |
| `/` | `space/holo/index.html` | Retained estate geometry, readable controls and an independent searchable source directory. |
| `/c2` | `space/c2/index.html` | Public synthetic operating picture, complete mobile event rail and explicit chain/verification states. |
| `/fabric` → `/holo/demo.html` | `space/holo/demo.html` | Retained shader engine inside a responsive page with source limits and a static failure state. |
| `/panels/` | `space/app.py::build_consoles` | All 21 existing Gradio panels, using supported Gradio 6 CSS/head mounting, native controls and the available viewport width. |

## Presentation and source boundaries

The exact KANCHAY 1.3 token file and the 24–48px native Orbit suite image come
from accepted `szl-holdings/szl-brand` source
`27d12e77fc0f9f1a0e5fae8b34adf2380d51d070`. The icon renders at 40px. Its
artwork remains CC BY 4.0; application code remains Apache-2.0.
`space/presentation/PROJECTION.json` records the exact two file lengths and
SHA-256 values. This is a local component design using the exact native assets,
not an assertion that every file in the shared design bundle is installed.

Opaque graphite or paper surfaces carry text, controls and receipts. The
historical geometry retains its own evidence colors and remains inside a
bounded visual frame. A visual glow is not a runtime status. The estate count
is explicitly the bundled historical topology, not a live organization census.
An HTTP response is labeled `RESPONSE RECEIVED`, with readiness and verification
still unknown. The science release links and separate PR38 candidate boundary
remain explicit.

The native directory is independent of Three and uses text nodes and bounded
record shapes. It remains navigable when the graphics library is unavailable.
Failed manifest reads leave an unavailable state and disable the filter; they
do not invent an empty estate. Theme storage denial is handled, and reduced
motion pauses autonomous graphics scheduling. The page can render again for a
resize or a deliberate interaction without restoring continuous animation.

Gradio keeps its own tab selection and overflow logic. Both measurement and
visible tabs use the same nonshrinking typography and dimensions; the overflow
menu has an opaque native surface. Numeric reset buttons retain their original
behavior with 44px targets. The wrapper removes duplicate framework padding on
mobile rather than hiding overflow or truncating controls. The skip link moves
focus to the console heading.

The original Gradio action bindings, backend/source functions, receipt math,
model behavior, authority, probe definitions and operational request shapes are
unchanged. The original shader engine, generated legacy fabric assets,
`estates.json`, `verticals.json` and archived source remain unchanged. The Space
card changes only the identity outside its protected technical body; its YAML
and complete protected body stay exact.

## C2 display correctness

C2 still generates and verifies public synthetic chains through the same
endpoints. Its local canonicalization, SHA-256 and chain recomputation functions
are unchanged. The event rail remains present on mobile. Response text is
rendered as text, and the display validates the expected event shape before
using it.

A new scenario clears the previous chain, receipt label and verification state.
Unavailable or malformed responses leave verification disabled. A delayed
verification result cannot label a newer scenario: the controller retains a
scenario version for the original request. Explicit verification sends the
same endpoint, headers and JSON body as before. No verification is initiated
automatically, and no failed request is retried automatically.

## Delivery through the existing writer

`space/presentation.py` exposes exactly five fixed public routes: token CSS,
local CSS, local controller, native icon and projection record. It checks and
reads the same no-follow file descriptor, rejects nonregular or oversized files
and uses fixed MIME types with `X-Content-Type-Options: nosniff`. Unknown paths
are not exposed by a general directory mount. Unavailable assets return a
plain 503 response.

The established publisher stages the full `space/` tree and emits
`szl-source-binding.json`, so the native subtree and helper are included without
adding a second writer. A source test stages that actual package, verifies the
native files and publisher declaration, then tampers with CSS and requires
source state `UNAVAILABLE`. A valid local binding remains
`LOCAL_BYTES_VERIFIED` / `PUBLISHER_DECLARED`, with GitHub attestation explicitly
`NOT_PERFORMED_AT_RUNTIME`.

No publication workflow, credential selector, target, lock, parent-CAS rule,
source/current-main gate or runtime verification is changed. The public and
private staging targets retain their existing separate controls. A source PR
and local browser results do not claim an immutable Hub publication or an
operationally qualified service.

## Qualification

The existing Python application and publisher suites remain in place. New
tests exercise the actual fixed asset responses, source/package closure,
unavailable file variants and source-tamper rejection. The Node controller
suite runs in memory and checks malformed/untrusted event display, stale chain
clearing and delayed verification results; it makes no network requests.

`tools/verify_constellation_browser.py` starts the actual ASGI/Gradio application
in a clean child environment, denies nonloopback transport and blocks operational
API routes and non-GET/HEAD requests. The browser loads the real four frontends
and all 21 actual Gradio tabs. It measures text contrast, labels, 44px controls,
horizontal reflow, available mobile console width, reduced motion and forced
colors. It also exercises locally labeled C2 synthetic/unavailable responses,
missing graphics libraries, empty filters, failed manifests and keyboard links.
It never clicks a Gradio computation, probe or verification action.

Three 0.160.0 may be supplied from the installed pinned package. Only ten fixed
module paths are fulfilled locally, and their observed hashes are recorded.
This validates rendering with those bytes; it does not validate CDN availability.
All other external browser requests are intercepted and denied. The report
records exact checkout identity, local changes and these fixture limits.

The read-only source CI extends its existing gates with the memory-only Node
suite and isolated Playwright/Three tools. Evidence is retained under
`RUNNER_TEMP` as unsigned browser observations, outside the published Space
payload. The original source, runtime, publisher, dependency and clean-tree
gates are preserved.

```sh
python tools/verify_constellation.py
python -m pytest -q space tools/tests
node --test space/tests/test_presentation_controller.cjs
python tools/verify_constellation_browser.py \
  --three-root /path/to/installed/three \
  --out /path/to/unsigned-observations
```

Use `--runtime-python` when the exact Space environment and the isolated
Playwright environment are separate. Provider publication and immutable/live
readback remain subsequent steps through the existing writer.
