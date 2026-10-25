# Regression Firewall — Roadmap

Version: 0.2 (2026-10-25)

Scope discipline: nothing on this list justifies speculative abstraction.
Items are built when they are built, behind the same deterministic-first
principles.

## V0.2 — Wider surface coverage — SHIPPED 2026-10-25

- [x] User-defined normalization rules (regex + key-hint) in config
      (`normalization.custom_rules`).
- [x] OpenAPI import: derive HTTP probes from an OpenAPI 3.x document
      (`surfaces.http.openapi`, preview via `import-openapi`).
- [x] CLI watched directories with ignore globs and a per-directory
      `max_files` cap (`surfaces.cli.probes[].dirs`).
- [x] Git diff integration: reports list which files changed since the
      baseline commit as a correlation hint — never used to classify
      changes as expected.
- JS/TS public API surface and better HTTP discovery moved to V0.3: both
  need real design time (static parsing without a Node dependency; route
  extraction by convention) and did not fit the release.

## V0.3 — Wider languages, environment behavior

- JavaScript / TypeScript public API surface (package exports, named
  exports, default export) via static parsing.
- Better HTTP discovery: route extraction from FastAPI/Flask apps by
  convention, not just explicit `discover.app` config.
- Filesystem behavior surface (beyond watched files/dirs): read/write footprints.
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
