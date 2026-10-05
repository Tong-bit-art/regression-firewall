# Regression Firewall — Roadmap

Version: 0.1 (2026-10-04)

Scope discipline: nothing on this list justifies speculative abstraction in
V0.1. Items are built when they are built, behind the same
deterministic-first principles.

## V0.2 — Wider surface coverage

- JavaScript / TypeScript public API surface (package exports, named
  exports, default export) via static parsing.
- OpenAPI import: derive HTTP probes from an OpenAPI document.
- Better HTTP discovery: route extraction from FastAPI/Flask apps by
  convention, not just explicit `discover.app` config.
- Git diff integration: surface-level hint of which files changed, used to
  *order* checks (never to classify changes as expected).
- Unknown generated-file detection for the CLI surface (watched directories
  with ignore globs).
- User-defined normalization rules (regex + key-hint) in config.

## V0.3 — Environment behavior

- Filesystem behavior surface (beyond generated files): read/write footprints.
- Configuration drift detection (config files that code reads).
- Environment variable read behavior for CLI probes.

## V0.4 — Data behavior

- Database surface: query count, write footprint, schema-sensitive reads.
- Potential N+1 detection (count-per-request heuristic).

## V0.5 — Selective regression analysis

- git diff + AST + dependency information → run only the behavior surfaces
  plausibly affected by the change. This is the performance unlock for large
  projects; it must never silently *skip* a surface that looks affected.

## V0.6 — Performance regression

- Repeat + median + variance-based timing thresholds with warm-up.
- Explicitly opt-in; timing is noise-prone and must default off.

## V1.0 — Maturity

- Stable snapshot format (v2 schema with migration tooling).
- CI integration mode (GitHub Action / generic CLI mode with artifacts).
- Multi-agent support validation matrix (Claude Code, Codex, Cursor,
  OpenCode, Gemini CLI).
- Plugin API for custom surfaces.
- Eval benchmark publishing (per-release detection metrics).

## Explicitly rejected for any version

- Auto-classifying unknown changes as intended (violates the intent model).
- LLM-only verdicts (violates verification-first).
- "Silence by default" modes that skip capture errors.
