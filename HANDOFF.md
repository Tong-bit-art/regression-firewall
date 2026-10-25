# Regression Firewall — Agent Handoff Document

**Handoff date:** 2026-10-25 (V0.2 development session; previous: 2026-10-07)
**Repo:** https://github.com/Tong-bit-art/regression-firewall (public)
**Working directory:** `D:\Regression Firewall Skill`
**Python:** 3.11.9 (system), 3.14.3 (uv-managed, use `py -V:Astral/CPython3.14.3 -m venv`)

---

## What This Project Is

A behavioral regression safety layer for AI coding agents. It captures
software behavior (HTTP/CLI/Python public API) before an AI code change,
captures again after, and reports unintended regressions with a
PASS/REVIEW/BLOCK verdict.

**Core principle:** Your tests prove the new code works. Regression Firewall
proves the old behavior still works.

## Current State (verified 2026-10-25, local Windows run)

| Suite | Result |
|---|---|
| pytest | **239 passed / 0 failed** (incl. benchmark-evaluator guards) |
| Bundled evals | **21/21** (recall 100%, FPR 0%, verdict 100%) |
| Real-world benchmark | 8 repos, 66 cases, 4 core bugs found & fixed (V0.1 code) |
| **Fresh holdout V0.3** | **21/21 PASS** on zod/isort/dateutil (recall 100%, FPR 0%, verdict 100%) — `docs/FINAL_HOLDOUT_V03.md`; executed 2026-10-25, gates the 0.3.0 release |
| **Fresh holdout V0.2** | **26/26 PASS** on tqdm/attrs/black (recall 100%, FPR 0%, verdict 100%) — `docs/FINAL_HOLDOUT_V02.md`; executed 2026-10-25, tool code 0.2.0 unchanged across all runs |
| Independent agent validation | **10/10 tasks, 0 hard-rule violations** (DeepSeek V4 Pro / OpenCode, 2026-10-07, V0.1 code) |

## Holdout V0.4 + release 0.4.0 (2026-10-26)

- **Fresh holdout** (datasette / pluggy / more-itertools, disjoint from all
  17 prior repos): **23/23 PASS** — recall 100% (10/10), FPR 0% (13/13),
  severity/verdict 100%. Caught one REAL V0.5 bug (selection crashed on
  venv-interpreter paths in probe commands — fixed + regression tested);
  benchmark infra gained `check_args` + `skipped_probes_min`.
  `docs/FINAL_HOLDOUT_V04.md`. Corpus consumed (avoid all 20 used repos
  next time).
- **v0.4.0 tagged and released** via the automated workflow.

## V0.5 + V0.6 (shipped 2026-10-25, on main — unreleased)

- **V0.5 `check --select`** — per-probe selective capture. `selection.py`
  maps the changed-file set (git) onto each probe's tracked paths
  (conservative; unknown deps always run); skipped probes are recorded in
  `report.selection` ({surface:{probe:reason}}) and can never yield a
  silent PASS (empty-capture guard forces REVIEW). run_capture grew
  `only_probes` filtering; diff suppresses deliberate-absence warnings per
  probe. Granularity limit: file-level mapping (sibling-file edits don't
  select).
- **V0.6 `probe.performance`** — opt-in timing budgets: warmup + timed
  repeats, sorted durations + median (ms) in the snapshot, median-ratio
  budget at diff time → `runtime_regressed` (MEDIUM/UNCERTAIN, never
  auto-BLOCK). Default off. Traces accumulate over all runs consistently.
- Suite at V0.6: 335 tests + 24/24 evals. At 0.4.0: 338 tests.

## V0.4 (shipped 2026-10-25, on main — unreleased)

- **`trace.sqlite`** on CLI probes: stdlib sqlite3 query shapes + counts +
  write-table footprint via the factory subclass hook (C types cannot be
  monkeypatched — subclassing works). Shapes normalized at capture time
  (`sqlshape.py`); count changes force REVIEW (the N+1 signal — added to
  UNCERTAIN_REVIEW_CATEGORIES in `scoring/risk.py`). New categories:
  db_query_added/removed, db_query_count_changed, db_table_written_added/
  removed (all UNCERTAIN). Honest scope: stdlib sqlite3 direct usage only.
- Suite at V0.4: 314 tests + 23/23 evals.

## V0.3 (shipped 2026-10-25, commit series on main)

- **Convention-based HTTP discovery** — `discovery/appdetect.py` (static
  scan, deterministic ranking) + `discover --emit-probes [MODULE:ATTR]`.
- **JS/TS public API surface (`js_api`)** — `js_exports.py` (static export
  extraction: ESM/CJS/alias lists/re-export resolution depth 3, comments+
  strings stripped) + `capture/js_api.py` + `diff/js_api.py`. New surface in
  config (`surfaces.js_api.probes[].file`), severity table, intent matcher.
- **CLI behavior tracing** — `trace.fs_writes` / `trace.env_reads` per probe;
  sitecustomize injected via PYTHONPATH (`capture/cli.py`,
  SITECUSTOMIZE_SOURCE); io.open AND builtins.open both wrapped (pathlib
  resolves io's binding); trace paths stored project-relative; env NAMES
  only, never values; non-Python commands skip tracing with a warning.
- Configuration-drift item deliberately closed by `files:` + tracing
  (documented in ROADMAP).
- Suite at V0.3.0: 297 tests + 22/22 evals (released as v0.3.0).

## V0.2 (shipped 2026-10-25)

- **OpenAPI import** — `surfaces.http.openapi` derives HTTP probes from an
  OpenAPI 3.x document at load time; `import-openapi` previews them.
  Implementation: `regression_firewall/config/openapi.py` (loaded by
  `config/loader.py`, schema in `config/schema.py`).
- **Custom normalization rules** — `normalization.custom_rules` (regex +
  optional key hints + placeholder). Compiled in `normalize/engine.py`.
- **CLI directory watching** — `surfaces.cli.probes[].dirs` (path, ignore
  globs, max_files cap with warning). Implementation: `capture/cli.py`.
- **Git diff hints** — reports list files changed since the baseline commit
  (`provenance.collect_changed_files`, report-only, never affects verdicts).
- Repo infrastructure: README badges, issue/PR templates, tag-driven
  `release.yml`, manual `publish.yml` (PyPI trusted publisher),
  `docs/RELEASE.md`, CI actions bumped to checkout@v5/setup-python@v6.

## Verdict Status

| Gate | Status |
|---|---|
| ENGINEERING READY | **YES** |
| BEHAVIOR DETECTION VALIDATED | **YES for V0.1 surfaces (with caveats); V0.2 additions covered by unit/integration tests + eval case 21, NOT yet by a real-repo benchmark run** |
| INDEPENDENT AGENT VALIDATED | **YES (V0.1 code)** — DeepSeek V4 Pro in OpenCode, fresh context; 10/10 protocol tasks, 0 hard-rule violations; findings in `docs/INDEPENDENT_AGENT_VALIDATION.md` |
| PUBLIC RELEASE READY | **YES (BETA)** — v0.2.0 tagged and released via the automated workflow |

## Architecture (key modules)

```
regression_firewall/
├── cli.py                 # argparse CLI: init/discover/baseline/check/report/explain
├── capture/
│   ├── base.py            # run_capture() orchestrator
│   ├── http_probe.py      # HTTP probes + ManagedServer lifecycle (RENAMED from http.py)
│   ├── cli.py             # CLI probes (subprocess)
│   ├── public_api.py      # Python introspection (subprocess api-runner)
│   └── _api_runner.py     # subprocess script: canonical signature fingerprint
├── config/
│   ├── schema.py          # typed dataclasses + validation (ConfigError)
│   ├── loader.py          # YAML/JSON loading, find_config_file
│   └── openapi.py         # OpenAPI 3.x → HTTP probe generation (V0.2)
├── diff/
│   ├── engine.py          # structural JSON diff (json_type, diff_json)
│   ├── http.py            # HTTP surface diff
│   ├── cli.py             # CLI surface diff
│   └── public_api.py      # public API diff
├── intent/
│   ├── model.py           # Intent, ExpectedChange
│   └── matcher.py         # classify_change() → expected/uncertain/unexpected
├── normalize/
│   ├── rules.py           # regexes, key hints, epoch/UUID/ISO/temp paths
│   └── engine.py          # Normalizer (JSON, headers, cookies, text)
├── scoring/
│   ├── severity.py        # severity table, confidence classes
│   └── risk.py            # score_changes() → score + verdict
├── report/
│   ├── console.py         # terminal output
│   ├── markdown.py        # report.md
│   └── json_report.py     # report.json
├── redact.py              # capture-time secret redaction
├── provenance.py          # git state, snapshot integrity hash
└── models/                # Snapshot, ProbeCapture, Change, CheckResult
```

## Critical Implementation Notes (DO NOT BREAK)

1. **`capture/http_probe.py`** (NOT http.py — renamed to avoid stdlib shadow).
   The api-runner subprocess runs in script mode with `sys.path[0]` = capture
   dir. Any module named `http.py` there shadows stdlib `http` and breaks
   ALL public-API captures on real projects.

2. **`_api_runner.py` uses `_canonical_signature()`** — NOT raw
   `str(inspect.signature())`. Framework callables (typer.Typer) have
   nondeterministic `Doc()` reprs in default values. The canonical
   fingerprint captures only: parameter names, kinds, default presence,
   annotation presence. Raw string comparison = systematic FP.

3. **`git clean -fdqx`** (with `-x`) in `mutations.py restore()` — without
   `-x`, .gitignore-matched files (e.g. `*.txt` in sherlock) survive clean
   and corrupt baselines.

4. **`PYTHONDONTWRITEBYTECODE=1`** in all tool-managed subprocesses —
   without it, stale `__pycache__` can cause false PASS (same-size,
   same-second edit passes pyc validation).

5. **`envsecret`/`set_api_key()` does NOT call save()** — healthchecks'
   `Project.set_api_key()` only sets the attribute; the benchmark's
   api_key_command must call `p.save()` explicitly after `set_api_key()`.

6. **CORS headers** (`Access-Control-Allow-Methods/Headers`) are
   set-semantic — Django emits them in nondeterministic order per process.
   Normalized by sorting in `normalize_headers()`.

7. **`{port}` must be substituted in server.command args**, not just
   base_url — Django's `runserver` takes the port as an argv argument.

8. **Intent paths normalize bracket indices**: `$.checks[0].desc` matches
   intent glob `checks.*.desc` via `_intent_path()` in the matcher.

## Benchmark System

```
benchmarks/
├── manifest.yaml               # validation corpus (8 repos)
├── manifest-holdout.yaml       # fresh holdout (3 repos: bottle, urllib3, packaging)
├── mutations/                  # per-repo mutation specs + ground truth
│   ├── flaskr.yaml, healthchecks.yaml, requests.yaml, click.yaml
│   ├── sherlock.yaml, typer.yaml, httpie.yaml, pip-tools.yaml
│   └── bottle.yaml, urllib3.yaml, packaging.yaml
├── runner/
│   ├── __main__.py             # python -m benchmarks.runner
│   ├── executor.py             # LocalExecutor (scrubbed env) / DockerExecutor (stub)
│   ├── mutations.py            # apply_mutation(), restore() with git clean -fdqx
│   └── report.py               # evaluate_case(), compute_metrics(), writers
└── results/                    # latest.json + history/
```

### Running benchmarks

```bash
export REGFW_BENCH_WORKSPACE=C:\regfw-bench  # MUST be ASCII-only path
python -m benchmarks.runner --split validation   # or --repo <id>
```

For the fresh holdout, swap the manifest:
```bash
cp benchmarks/manifest-holdout.yaml benchmarks/manifest.yaml
python -m benchmarks.runner --split holdout
cp benchmarks/manifest-validation-backup.yaml benchmarks/manifest.yaml
```

### Fresh holdout status

The fresh holdout was run once:
- **bottle**: 5/5 PASS (100% recall, 0% FPR)
- **urllib3**: 4/7 (controls pass, 3 symbol mutations miss — src/-layout
  editable install issue: the api-runner subprocess may not resolve the
  package correctly through the meta-path finder)
- **packaging**: 1 REPOSITORY_SETUP_FAILURE (verify step import fails)

These are the ORIGINAL fresh holdout results. If bugs are fixed, re-run
results must be labeled "POST-FIX VALIDATION", not "holdout".

## Remaining Work

| Item | Priority | Status |
|---|---|---|
| New fresh holdout | HIGH (before the next release cycle) | **DONE for V0.3** (2026-10-25): zod/isort/dateutil, 21/21 PASS, zero tool bugs — `docs/FINAL_HOLDOUT_V03.md`; released as v0.3.0. Corpus CONSUMED: the next holdout must avoid all 17 used repos. |
| PyPI publication | MEDIUM | Everything is prepared: `publish.yml` (manual, OIDC Trusted Publisher) + `docs/RELEASE.md`. BLOCKED on the repo owner doing the one-time PyPI side: add the pending trusted publisher (owner=Tong-bit-art, repo=regression-firewall, workflow=publish.yml, env=pypi) and create the `pypi` environment in repo settings. Then tag a release and run the workflow. |
| Benchmark-infra hardening done in holdout | — | `build_wheel` purges stale wheels; `ExpectedEntry` supports `path` (+ tests). Workspace lesson: never `clean_excludes` a dir the setup re-creates — state leaks across runs (documented in FINAL_HOLDOUT_V02). |
| CI maintenance | LOW | **DONE 2026-10-25**: checkout@v5, setup-python@v6. |
| typer.Typer signature: full fix | LOW | Canonical fingerprint works for most cases; edge cases with rich-conditional imports still UNSUPPORTED |
| Cross-vendor agent validation on V0.2 | LOW | Independent agent validation ran on V0.1 (2026-10-07); repeat on V0.2 with a different vendor when convenient. |
| V0.3 features | MEDIUM | JS/TS public API surface, better HTTP discovery, filesystem/env behavior (`docs/ROADMAP.md`). |

## Key Files to Read First

1. `README.md` — product overview, honest claims
2. `docs/PRD.md` — product requirements
3. `docs/ARCHITECTURE.md` — design decisions D1-D5
4. `docs/BEHAVIOR_MODEL.md` — surfaces, categories, severity table
5. `docs/DEVELOPMENT_LOG.md` — full history of bugs found & fixed
6. `docs/BENCHMARK_RESULTS.md` — real-world benchmark evidence
7. `docs/HISTORICAL_REGRESSIONS.md` — real regression analysis
8. `SKILL.md` — agent workflow contract
9. `docs/INDEPENDENT_AGENT_VALIDATION.md` — executed validation record
   (10/10 tasks, findings, raw evidence pointer)

## Known Limitations (documented, not fixable in V0.1)

1. No Docker isolation (scrubbed env only)
2. Post-hoc intent detection anchors on check runs (the tool cannot observe
   when code was actually edited); artifact deletion is forbidden by the
   skill and mitigated by report+journal redundancy
3. CLI free-text secrets can't be reliably scanned
4. Cookie value-level changes hidden by default redaction
5. ISO date rule masks stable business dates (e.g. date_of_birth)
6. Re-baselining after edits can't be distinguished from legitimate use
7. Public API behavioral changes within method bodies not detected
8. No FastAPI app in benchmark corpus
9. Independent validation was a single same-machine agent run (DeepSeek in
   OpenCode, 2026-10-07); no cross-vendor field trial yet
10. Module-level imported helpers count as public namespace (consistent with
    `dir()` semantics; can be noisy in refactors)
