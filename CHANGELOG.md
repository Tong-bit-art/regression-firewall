# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Database behavior tracing (V0.4).** Per-probe opt-in `trace.sqlite`
  records stdlib sqlite3 usage through the documented factory subclass
  hook (C types cannot be monkeypatched; they are subclassable):
  statements are normalized to SHAPES at capture time (literals -> `?`,
  `IN`-lists collapsed, comments/whitespace removed) with per-shape
  counts, plus a best-effort write-table footprint. New categories:
  db_query_added / db_query_removed (MEDIUM), db_query_count_changed
  (LOW, forces REVIEW — the count-per-run N+1 signal for CLI jobs),
  db_table_written_added / db_table_written_removed (MEDIUM); all
  UNCERTAIN. Honest scope: stdlib sqlite3 direct usage only — other
  drivers, ORMs, and network databases are invisible (documented);
  HTTP-request-scoped N+1 detection remains a roadmap item.
- Eval case 23 (`cli_trace_sqlite_count`): N+1-style count signal.
  Suite is now 23 cases.

- **Official GitHub Action (CI integration mode — V1.0 item pulled
  forward).** Composite action (`action.yml`): checks out the PR base ref,
  captures a fresh behavior baseline, runs `check` on the head ref, maps
  PASS/REVIEW/BLOCK to job conclusions (`fail-on: block|review`), writes
  the Markdown report to the job summary, and uploads report artifacts.
  Inputs for project path, committed or inline intent, project dependency
  install, and tool install override. Validated end-to-end by a dogfood
  workflow (`.github/workflows/action-demo.yml`): a PASS job plus a BLOCK
  job against the `ci/action-demo-block` fixture branch with a planted
  exit-code regression. Two integration issues found and fixed during
  local simulation: `examples/cli/deploy.py` crashed when `out/` was
  missing, and absolute checkout paths embedded in CLI output produced
  structural false positives across the two checkouts — the CLI capture
  now rewrites the probe's working directory to `.` in stdout/stderr
  (capture-time, deterministic, unit-tested).

## [0.3.0] - 2026-10-25

Wider languages and behavior visibility: JS/TS public API surface,
opt-in CLI behavior tracing, convention-based HTTP discovery.

### Added

- **JS/TS public API surface (`js_api`).** Static, zero-dependency export
  extraction for entry files: ESM named exports (functions, classes,
  consts/lets/vars incl. arrow signatures, interfaces, types, enums),
  `export default` (with signature when the default is a named function),
  alias lists, CommonJS `exports.NAME` / `module.exports.NAME`, and
  relative re-export resolution to depth 3 with cycle guard
  (`export {x as y} from`, `export * from`, `export * as ns from`).
  Comments and string contents are stripped before matching so doc text
  cannot invent exports. New categories mirror public_api:
  symbol_removed (critical), symbol_added (info), signature_changed and
  export_changed (medium), capture_error (high). Conservative scope is
  documented — anything the parser cannot see is invisible, never guessed.
- **CLI behavior tracing.** Per-probe opt-in `trace.fs_writes` /
  `trace.env_reads` records which paths a probe command writes and which
  environment-variable NAMES it reads (values never captured) by injecting
  a sitecustomize.py via PYTHONPATH — Python commands only, stated loudly
  when tracing is skipped. New categories: fs_write_added /
  fs_write_removed (medium), env_read_added / env_read_removed (low); all
  UNCERTAIN, so tracing findings drive REVIEW, never silent PASS or
  outright BLOCK. Write paths under the project are stored project-relative
  (portable snapshots).
- **Configuration-drift detection decision.** Covered by the existing
  `files:` watch plus the tracer's write visibility; a separate mechanism
  was deliberately not built (documented in docs/ROADMAP.md).
- **Convention-based HTTP app discovery (V0.3 first item).** `discover`
  lists FastAPI/Flask/Starlette app instances found by a static scan
  (imports nothing); `discover --emit-probes [MODULE:ATTR]` imports the app
  in an isolated subprocess and prints ready-to-paste HTTP probes from its
  **real routes** — spec defaults to the best-ranked candidate. Routes with
  path parameters (`{id}` / `<int:id>`) are excluded with a note pointing at
  the OpenAPI import for concrete values. Detection never executes project
  code; only the explicitly chosen app is imported, exactly like a
  configured `discover_app`.
- Eval case 22 (`cli_trace_fs_write`): traced write-target regression with
  env-read noise control. Suite is now 22 cases.
- **Fresh holdout on V0.2 code (2026-10-25).** New 3-repo corpus (tqdm,
  attrs, black — CLI, public-API src-layout, and the V0.2 directory-watch
  path), 26 cases: detection recall 100% (12/12), FPR 0% (14/14 controls),
  severity and verdict accuracy 100%. Tool code unchanged across all runs;
  every intermediate failure was benchmark authoring/infrastructure and is
  documented in `docs/FINAL_HOLDOUT_V02.md`. Corpus consumed — the next
  release cycle needs a fresh one.
- Benchmark runner hardening found by the holdout: stale wheels in the
  workspace dist/ are purged before building (a leftover wheel could
  silently benchmark the wrong tool version); ground-truth entries support
  a `path` field for generated-file cases (+ regression tests).

### Fixed

- Benchmark runner: `REGFW_BENCH_WORKSPACE` handling documented (ASCII-only;
  Git Bash needs forward slashes — `C:/regfw-bench`, not `C:\\regfw-bench`).

## [0.2.0] - 2026-10-25

Wider surface coverage: OpenAPI-derived probes, user-defined normalization,
CLI directory watching, and git correlation hints in reports.

### Added

- **OpenAPI import.** `surfaces.http.openapi` derives HTTP probes from an
  OpenAPI 3.x document (YAML/JSON) at config load time; explicit probes win
  on id conflicts; `{path}` parameters take values from `set:` (default
  `1` with a warning). `regression-firewall import-openapi` previews the
  generated probes. Swagger 2.x and pathless documents are loud config
  errors. See `docs/OPENAPI_IMPORT.md`.
- **Custom normalization rules.** `normalization.custom_rules` masks
  project-specific volatile data: regex pattern (full-match for keyed
  values, `re.sub` for plain text), optional key hints, angle-bracketed
  placeholder. Rules are validated (unique lowercase names, compilable
  patterns), run before built-in rules, and are part of the config hash.
- **CLI directory watching.** `surfaces.cli.probes[].dirs` watches whole
  directory trees with fnmatch ignore globs (whole subtrees pruned) and a
  deterministic per-directory `max_files` cap (truncation warns). New,
  modified, and deleted files under a watched directory are detected like
  watched files.
- **Git diff hints in reports.** `check` reports which files git saw change
  since the baseline commit (committed diffs + dirty working tree, capped
  at 200, tool artifacts filtered). Correlation hint only — it never feeds
  classification, scoring, or the verdict.
- GitHub issue/PR templates; tag-driven release workflow (tag/version
  consistency check, changelog-derived release notes, wheel smoke test) and
  a manual PyPI publish workflow via Trusted Publishers (docs/RELEASE.md).
- Eval case 21 (`cli_dir_watch_created`): directory-watch detection plus
  ignore-glob noise control. Suite is now 21 cases.

### Fixed

- CI: `actions/checkout@v4` / `actions/setup-python@v5` bumped to v5/v6
  (Node 20 deprecation warnings).

## [0.1.1] - 2026-10-07 (never tagged; work shipped on main)

Release-blocker closure.

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
