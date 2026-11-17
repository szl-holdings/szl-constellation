# Third-party WebGL vendor inventory

- Upstream: https://github.com/mrdoob/three.js
- npm package: `three@0.187.0`, observed 2026-11-17
- npm archive SHA-1: `face29ee2de9bcc31a1b573a76f224e35e0b2894`
- License: MIT, copyright Three.js authors; verbatim license in `THREE-LICENSE.txt`
- Vendored files and SHA-256:
  - `three.module.js`: `104f56145899722094556490d787aae0617cc2fc3382f31df02d724ea1aee341`
  - `three.core.js`: `613e370f76638fdef83926642bf256dc9615684922de1ce1f63a8583e5d78578`
  - `OrbitControls.js`: `a747d56dd959510407777f1800792b2b52c0a435980fd6e40caf303d8a674b9e`
  - `THREE-LICENSE.txt`: `8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc`

Adaptation: in `OrbitControls.js`, the bare upstream `from 'three'` import
was changed to `from './three.module.js'` for a same-origin, no-import-map,
no-CDN static deployment. No other upstream runtime source modifications.
A browser build with any different digest must fail the project vendor-pin gate.

This code is WebGL rendering only. It contains no private Hugging Face
metadata, models, dataset rows, medical records, deployment secrets or keys.
