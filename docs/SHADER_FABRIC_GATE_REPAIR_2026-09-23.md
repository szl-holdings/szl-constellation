# Shader Fabric gate repair — 2026-09-23

## Finding

The prior validator rejected the source because a historical comment mentioned a removed
feedback-shader symbol. It did **not** detect executable dead code.

## Repair

- Rephrased the historical comment without the forbidden symbol.
- Replaced broad text matching with executable-pattern checks:
  - no feedback shader constant declaration;
  - no unbound feedback sampler declaration;
  - no undefined texture-size placeholder;
  - no legacy non-ASCII class identifier;
  - fail-closed estate validator and static fallback required.

## Result

The source passes the corrected v1.1 Shader Fabric hygiene gate.

## Boundary

This is a source repair only. It does not claim Hugging Face runtime deployment,
source/runtime convergence, performance, or production readiness.