# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-04

First release. Core workflow: `baseline` → (code + intent) → `check`.

### Added

- CLI: `init`, `discover`, `baseline`, `check`, `report`, `explain`.
- Behavior surfaces:
  - **HTTP** — status, headers, cookies, JSON body (structured), content-type;
    GET/POST/PUT/PATCH/DELETE; optional managed server lifecycle with
    `{port}` template and `REGFW_SERVER_PORT`.
  - **CLI** — stdout, stderr, exit code, watched generated files.
  - **Public API (Python)** — importable symbols, kinds, signatures,
    `__all__`, submodules (via isolated subprocess introspection).
- Normalization engine: UUID, ISO datetime, epoch timestamps (with temporal
  key hints), request IDs, tokens/secrets, temp paths, durations, float
  precision, whitespace/ANSI cleanup; per-rule config switches; header and
  JSON-path ignores.
- Capture-time secret redaction (`redaction.secrets`, on by default):
  auth-related headers, cookie values, and secret-named body fields are
  masked in stored snapshots.
- Structural JSON diff with JSON-path locations and stable change IDs.
- Intent files (`intent.json`) with deterministic EXPECTED/UNCERTAIN/
  UNEXPECTED classification.
- Risk model: per-category severities with overrides, explainable additive
  score, PASS/REVIEW/BLOCK verdict rules with consistency floors.
- Reports: terminal, Markdown (`report.md`), JSON (`report.json`).
- Eval suite: 20 deterministic end-to-end cases (recall 100%, FPR 0%,
  verdict accuracy 100% on the suite).
- Agent Skill (`SKILL.md`) with the baseline → intent → check workflow and
  anti-gaming rules.
- Docs: PRD, architecture, behavior model, normalization, risk model, eval
  methodology, roadmap, skill design.
- CI: GitHub Actions across Linux/macOS/Windows and Python 3.9–3.13.

### Hardening (release audit + RC hardening)

- Snapshots no longer store secrets (capture-time redaction); see SECURITY.md.
- Stale `__pycache__` can no longer cause false PASS in tool-managed runs.
- `ignore.json_paths` now suppresses all changes at ignored paths.
- Binary response size changes are detected; `--intent` typos fail loudly;
  wildcard-intent entries announce themselves in reports.
- Baseline provenance: git commit/dirty state (graceful outside git),
  snapshot integrity hash, tamper detection on `check`.
- Re-baseline guard: replacing a baseline whose last check reported
  BLOCK/REVIEW requires `--force` and flags later checks with a
  BASELINE TRUST WARNING.
- Epoch timestamps under `ts`/`*_ts`/`*_ms` keys are normalized (0/10
  false positives in no-change stability loops).
- CI matrix (Ubuntu/Windows/macOS, Python 3.11–3.13) including a
  build-and-install-from-wheel step; `flask` declared as a dev dependency.
