# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — release-blocker closure (2026-10-07)

### Added

- **Intent audit trail (P0).** The intent state is recorded at baseline and
  at every check. Entries that first appear (or are modified) after a
  previous check already observed the behavior are POST-HOC: they are
  marked in the report, keep the verdict at REVIEW, and are cumulative
  until explicitly acknowledged with `check --accept-post-hoc-intent`.
  An append-only `intent_audit.jsonl` journal backs the audit trail if
  `report.json` is rotated or deleted; the re-baseline guard reads it too.
- **No-evidence guard (P0).** A probe that fails at both baseline and check
  can no longer yield a silent PASS: the verdict is kept at REVIEW and the
  report says the probe was NOT verified. Failed captures are warned about
  at capture time as well.
- `tests/fixtures/src_layout_package/` — minimal standard src-layout fixture
  with regression coverage for removal/addition/signature/no-op/stability.

### Fixed

- **Standard src-layout public-API coverage (P0).** The introspection
  subprocess now adds the project's own `src/` root, so `src/<pkg>` projects
  (urllib3, packaging, …) are captured from the working tree.
- `symbol_removed` classification for names declared in `__all__` that can
  no longer be resolved (previously misreported as a signature change).
- Symbol enumeration now uses the module namespace (`vars`) — modules with a
  restrictive `__dir__` (e.g. `packaging.version`) no longer hide importable
  symbols.
- Benchmark runner: `setup_commands` / `verify_command` / `api_key_command`
  written as plain strings now fail loudly instead of being iterated
  character-by-character into `python -` (silent no-op); the repo setup is
  re-applied after each per-case restore (build-generated files such as
  urllib3's `_version.py` are recreated); the working tree is restored
  before setup as well as per case.
- Benchmark fixture corrections (benchmark hygiene, ground truth preserved):
  urllib3 signature mutation produced invalid Python (second `*`) and was
  corrected; packaging probes now cover `packaging.version`.

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
- Full matrix verified green on real GitHub Actions runners, including
  macOS (where fixture servers were fixed to avoid a 35s reverse-DNS hang
  in `HTTPServer.server_bind` on runner VMs).
