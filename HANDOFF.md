# Regression Firewall — Agent Handoff Document

**Handoff date:** 2026-10-26
**Frozen release:** **v0.4.0** (tag `v0.4.0`, commit `9301026`, GitHub Release published)
**Repo:** https://github.com/Tong-bit-art/regression-firewall (public)
**Working directory:** `D:\Regression Firewall Skill`
**Python:** 3.11.9 (system, primary verification), 3.14.3 (uv-managed,
`py -V:Astral/CPython3.14.3 -m venv`); CI matrix covers 3.11–3.13 on
Ubuntu/Windows/macOS
**Benchmark workspace:** `C:\regfw-bench` (MUST be ASCII-only; in Git Bash
write the env var as `REGFW_BENCH_WORKSPACE=C:/regfw-bench` — backslashes
get eaten)

---

## What This Project Is

A behavioral regression safety layer for AI coding agents. It captures
software behavior (HTTP / CLI / Python public API / JS-TS exports / traced
filesystem-env-sqlite behavior) before an AI code change, captures again
after, and reports unintended changes with a deterministic PASS / REVIEW /
BLOCK verdict. No LLM anywhere in the pipeline.

**Core principle:** Your tests prove the new code works. Regression
Firewall proves the old behavior still works.

## Current State (verified 2026-10-26, at commit `9301026`)

| Suite | Result |
|---|---|
| pytest | **338 passed / 0 failed** |
| Bundled evals | **25/25** (recall 100%, FPR 0%, severity 100%, verdict 100%) |
| CI matrix | **7/7 green** (Ubuntu 3.11–3.13, Windows/macOS 3.12–3.13) + green dogfood workflow |
| Fresh holdout V0.4 | **23/23 PASS** on datasette/pluggy/more-itertools (`docs/FINAL_HOLDOUT_V04.md`) |
| Fresh holdout V0.3 | **21/21 PASS** on zod/isort/dateutil (`docs/FINAL_HOLDOUT_V03.md`) |
| Fresh holdout V0.2 | **26/26 PASS** on tqdm/attrs/black (`docs/FINAL_HOLDOUT_V02.md`) |
| Real-world benchmark (V0.1) | 8 repos, 66 cases, recall 100%, FPR 0% |
| Independent agent validation | **10/10 tasks, 0 hard-rule violations** (DeepSeek V4 Pro / OpenCode, 2026-10-07, V0.1 code) |
| GitHub Action | shipped + **dogfooded** (PASS job + planted-regression BLOCK job, both green) |
| PyPI | **NOT published** — owner scheduled it for 2026-10-26; `publish.yml` (manual, OIDC Trusted Publisher) is ready |

## Release History

| Tag | Date | Contents |
|---|---|---|
| v0.1.0 | 2026-10-04 | core workflow, HTTP/CLI/public-API surfaces, eval system |
| v0.2.0 | 2026-10-25 | OpenAPI import, custom normalization rules, CLI directory watching, git-diff hints |
| v0.3.0 | 2026-10-25 | convention-based HTTP discovery (`discover --emit-probes`), **js_api surface** (static JS/TS exports), CLI behavior tracing (fs_writes / env_reads) |
| v0.4.0 | 2026-10-26 | **trace.sqlite** (query shapes/counts/write tables), **`check --select`** (per-probe selective capture), **`probe.performance`** (median-ratio runtime budgets), official GitHub Action, holdout-validated |

The ENTIRE V0.1–V0.6 roadmap is shipped. Remaining V1.0 items (snapshot
schema v2, plugin API, multi-vendor agent matrix) are deliberately deferred
as speculative until a driving need exists — do not build them speculatively
(project principle #5).

## Architecture (key modules)

```
action.yml                    # composite GitHub Action (CI integration)
regression_firewall/
├── cli.py                    # argparse CLI: init/discover(+--emit-probes)/
│                             #   baseline/check(+--select)/report/explain/
│                             #   import-openapi; INIT_TEMPLATE; EXIT codes
│                             #   0/1(REVIEW)/3(BLOCK)/2/70
├── js_exports.py             # static JS/TS export extraction (ESM/CJS/
│                             #   aliases/re-export resolution depth 3)
├── sqlshape.py               # deterministic SQL shape normalization
├── selection.py              # V0.5 per-probe dependency mapping + decisions
├── provenance.py             # git state, snapshot integrity hash,
│                             #   collect_changed_files (git hints + --select)
├── redact.py                 # capture-time secret redaction (HTTP only)
├── capture/
│   ├── base.py               # run_capture orchestrator (+ only_probes filter)
│   ├── http_probe.py         # HTTP probes + managed server  ← NOT http.py
│   ├── cli.py                # CLI probes: files/dirs watching, SITECUSTOMIZE
│   │                         #   tracer (fs_writes/env_reads/sqlite), timing
│   │                         #   loop (performance), cwd relativization
│   ├── public_api.py         # Python introspection (subprocess)
│   ├── _api_runner.py        # subprocess script: canonical signature FP
│   └── js_api.py             # static js_api capture (no execution)
├── config/
│   ├── schema.py             # typed dataclasses + validation; 4 surfaces
│   │                         #   (http/cli/public_api/js_api) + trace +
│   │                         #   performance + openapi + custom_rules
│   ├── loader.py             # YAML/JSON load; openapi probe generation
│   └── openapi.py            # OpenAPI 3.x → HTTP probes
├── discovery/
│   ├── project.py            # language/framework detection
│   ├── appdetect.py          # convention-based app detection (static scan)
│   ├── routes.py             # subprocess route extraction wrapper
│   └── _route_runner.py      # FastAPI/Starlette/Flask route enumeration
├── diff/
│   ├── engine.py             # structural JSON diff, make_change
│   ├── http.py / cli.py / public_api.py / js_api.py
│   └── __init__.py           # diff_surfaces (+ skipped_probes suppression)
├── intent/
│   ├── model.py              # Intent, ExpectedChange
│   ├── matcher.py            # classify_change; UNCERTAIN_CATEGORIES
│   └── audit.py              # post-hoc intent audit + journal
├── normalize/
│   ├── rules.py              # built-in regexes/key hints
│   └── engine.py             # Normalizer (custom rules run FIRST)
├── scoring/
│   ├── severity.py           # DEFAULT_SEVERITY per (surface, category),
│   │                         #   POINTS, VALUE_LEVEL/STATE confidence
│   └── risk.py               # score_changes: verdict rules + floors;
│                             #   UNCERTAIN_REVIEW_CATEGORIES (count changes
│                             #   and stdout/stderr/header force REVIEW)
└── report/
    ├── console.py / markdown.py / json_report.py
    └── _explain.py           # why_it_matters / recommended_action
benchmarks/                   # real-repo benchmark system (see §Benchmarks)
evals/                        # 24 deterministic end-to-end cases
docs/                         # PRD, ARCHITECTURE, BEHAVIOR_MODEL,
                              #   NORMALIZATION, RISK_MODEL, EVALS, CI,
                              #   OPENAPI_IMPORT, RELEASE, FINAL_HOLDOUT*.md
tests/                        # 338 tests (unit + integration + eval wrapper)
examples/                     # fastapi / flask / cli / python-library
.github/                      # test.yml (7-job matrix), release.yml,
                              #   publish.yml (PyPI, manual), action-demo.yml
```

## Critical Implementation Notes (DO NOT BREAK)

Capture and detection integrity:

1. **`capture/http_probe.py`** (NOT `http.py`): the api-runner subprocess
   runs in script mode; a module named `http.py` in the capture dir shadows
   stdlib `http` and breaks ALL public-API captures on real projects.
2. **`_api_runner.py` uses `_canonical_signature()`** — never raw
   `str(inspect.signature())`. Framework callables (typer.Typer) have
   volatile default reprs; the canonical fingerprint captures parameter
   names/kinds/optional/rest only.
3. **`PYTHONDONTWRITEBYTECODE=1` in every tool-managed subprocess** — stale
   `__pycache__` can cause false PASS (same-size, same-second edits pass
   pyc validation).
4. **CLI capture relativizes the probe CWD in stdout/stderr**
   (`_relativize_text`): in CI the baseline/check run in two different
   checkout dirs; absolute paths inside tracebacks would otherwise diff
   structurally. Stored snapshots are therefore cwd-independent.
5. **Tracer (sitecustomize injection)**: when adding a trace flag you MUST
   update BOTH the trace-setup condition (`if trace and (...)`) AND the
   data-keys condition in `_run_probe` — a missed one yields silent empty
   traces (this bit us with `trace.sqlite`).
6. **`io.open` AND `builtins.open` are both wrapped** by the tracer — they
   are the same object but separate namespace bindings, and pathlib
   resolves the io module's binding at call time.
7. **sqlite3 tracing uses the documented `factory` subclass hook** —
   Cursor/Connection are C extension types; monkeypatching raises, but
   subclassing works. Only `sqlite3.connect()` calls made AFTER injection
   are traced.
8. **Custom normalization rules run BEFORE built-in rules** (user patterns
   win); they are part of the config hash.
9. **js_exports.py**: TypeScript `.js`→`.ts` specifier mapping is REQUIRED
   for real barrels (zod); generics between name and params
   (`function f<T>(...)`) and type-annotated consts (`export const x: T =`)
   must keep parsing; comments AND string contents are stripped before
   matching; re-export resolution is depth-3 with cycle guard. Scope rule:
   anything the parser cannot see is invisible — never guessed.
10. **selection.py (V0.5)**: the interpreter token (command[0]) and
    absolute path tokens are NOT project dependencies (they are
    environment — `{venv_python}` renders to a path outside the project and
    used to crash `relative_to`); out-of-project dependency labels keep
    their absolute form (`_rel_label`). Unknown dependencies ALWAYS run.
    Every skip is recorded in `report.selection` ({surface:{probe:reason}});
    a check that skips everything cannot PASS.
11. **Performance budgets are RATIO-based** (median_after / median_before >
    max_ratio), never absolute milliseconds; `runtime_regressed` is
    MEDIUM/UNCERTAIN — forces review, never auto-BLOCK. Default OFF.
12. **Anti-gaming guards (never weaken)**: re-baseline guard (`--force` +
    BASELINE TRUST WARNING); post-hoc intent audit
    (`--accept-post-hoc-intent`, append-only journal); no-evidence guard
    (failed-both-sides probes and fully-skipped selective checks cannot
    PASS); capture-time redaction; config-hash change warnings; UNCERTAIN
    categories never auto-BLOCK.

Cross-platform:

13. PowerShell does not expand globs → `shell: bash` on Windows CI steps.
14. macOS runner VMs: ~35s `socket.getfqdn()` reverse-DNS hang blocks
    `HTTPServer.server_bind` — fixture servers override `server_bind`.
    Third-party servers (e.g. managed `flask run` = werkzeug) cannot be
    patched from the tool; managed-server e2e tests that launch them are
    `skipif(sys.platform == "darwin")` (see test_init_autoconfig.py).
15. HTTP probes bypass proxies via `ProxyHandler({})` (local Clash :7890).
16. setuptools `build/` accumulates stale files — the runner and release
    flow clean before building; **the benchmark runner also purges stale
    wheels from the workspace `dist/`** (a leftover 0.1.0 wheel once won
    the glob and would have benchmarked the wrong version).
17. `git clean -fdqx` (with `-x`) for mutation restore. **NEVER
    `clean_excludes` a directory that setup re-creates** — generated state
    leaks across cases/runs (observed in the V0.2 holdout).

## Benchmarks (real-repo validation)

```
benchmarks/
├── manifest.yaml                     # ACTIVE manifest (swapped for runs)
├── manifest-validation-backup.yaml   # the 8-repo validation corpus
├── manifest-holdout.yaml             # V0.1-era holdout (consumed)
├── manifest-holdout-v02/03/04.yaml   # archived holdout manifests
├── mutations/<repo>.yaml             # per-repo cases + ground truth
├── runner/                           # __main__ / executor / mutations / report
└── results/                          # latest.json + history/ (git-tracked)
```

- Run: swap the desired manifest over `manifest.yaml`, then
  `REGFW_BENCH_WORKSPACE=C:/regfw-bench python -m benchmarks.runner --split holdout`
  (or `--repo <id>`); restore `manifest-validation-backup.yaml` afterwards.
- Case schema: `edits` (find/replace, `replace_all` optional),
  `apply_before_baseline` (noise cases), `check_args` (e.g. `["--select"]`),
  `expected: {changes: [...], verdict, skipped_probes_min}`.
- **Ground truth is authored against reality**: run the real parser /
  commands on the real checkout BEFORE freezing (every holdout found its
  authoring bugs this way); a wrong `find` string may be fixed, an
  expectation may not. Runs after tool fixes must be labeled POST-FIX
  VALIDATION. Holdout discipline: run once; if tool bugs are found, fix and
  create a NEW corpus.
- **Consumed repos (20) — a new holdout must avoid all of them:**
  flaskr(flask), healthchecks, requests, click, sherlock, typer, httpie,
  pip-tools, bottle, urllib3, packaging, tqdm, attrs, black, zod, isort,
  dateutil, datasette, pluggy, more-itertools.
- Holdout ledger: V0.1-era 3 repos (consumed 2026-10-07); V0.2 26/26
  (2026-10-25); V0.3 21/21 (2026-10-25); V0.4 23/23 (2026-10-26 — caught a
  real V0.5 selection crash on venv-interpreter paths, fixed + tested).

## Evals & the GitHub Action

- `python -m evals.runner` — 25 cases (V0.4 added sqlite count signal,
  V0.6 added runtime regression). Also wired into pytest and CI.
  `tests/integration/test_evals.py` derives the case count from disk —
  never pin the number.
- `action.yml` (composite GitHub Action): dual checkout → baseline on
  base-ref → check on head-ref → verdict→conclusion mapping
  (`fail-on: block|review`), report in `$GITHUB_STEP_SUMMARY`, artifacts.
  Dogfooded by `.github/workflows/action-demo.yml`: PASS job on
  `examples/cli` + BLOCK job against fixture branch `ci/action-demo-block`
  (one planted exit-code regression; keep it minimal, rebase onto main
  when examples/cli changes).
- Action check-step gotcha (fixed once, do not regress): the step runs with
  `working-directory: .regfw-head`, so the baseline must be copied from
  `$GITHUB_WORKSPACE/.regfw-base/...`, not a sibling-relative path.

## Release Process

See `docs/RELEASE.md`. Short form: tests + evals green → fold CHANGELOG
`[Unreleased]` into `[<version>] - <date>` → bump `pyproject.toml` version
→ commit/push → tag `v<version>` and push the tag → `release.yml` verifies
tag==version, extracts changelog notes, builds + smoke-tests the wheel, and
publishes the GitHub Release. PyPI: `publish.yml` (manual) after the
one-time Trusted Publisher setup (owner=Tong-bit-art, workflow=publish.yml,
environment=pypi) — **owner scheduled this for 2026-10-26**.

## Remaining Work

| Item | Priority | Notes |
|---|---|---|
| PyPI publication | HIGH (owner) | one-time trusted publisher + `pypi` environment, then run `publish.yml`; publishes v0.4.0 |
| New fresh holdout | before NEXT release | avoid all 20 consumed repos; corpus ideas: an ORM-backed CLI (exercises sqlite limits honestly), a FastAPI app repo (HTTP), a JS repo if js_api changes |
| Cross-vendor agent validation on v0.4 | LOW | 2026-10-07 run was DeepSeek on V0.1 code; needs an external agent vendor |
| Snapshot schema v2 + migration | DEFERRED | format is unchanged since v0.1; no driving need (speculative abstraction) |
| Plugin API for custom surfaces | DEFERRED (design written) | no consumer evidence yet; implementation path now written in `docs/PLUGIN_API_PROPOSAL.md` — phase 1 (internal Surface protocol refactor) is the shippable first step |
| Multi-agent validation matrix | DEFERRED | requires external vendors |
| Per-release metric publishing | DONE 2026-10-26 | release.yml runs pytest+evals as a release gate and attaches `summary.json` + a metrics table to every GitHub Release |
| Action PR comments | DONE 2026-10-26 | `comment: true` posts/updates a marker-matched PR comment with the full report; dogfood pass-path validates it on PRs |

## Known Limitations (honest, documented in README/docs)

1. Detection covers only probe-configured behavior; nothing else.
2. js_api is static and conservative: minified code, dynamic exports,
   destructured exports, bundler aliases, object-literal `module.exports`,
   class members, `export =` — invisible, never guessed.
3. Tracing is Python-only and stdlib-grade: no ORMs/drivers/network DBs,
   no `os.fdopen` writes, non-Python child processes untraced.
4. `--select` mapping is file-level: sibling-file edits do not select a
   probe; unknown dependencies always run (by design).
5. Timing budgets are machine-relative; baseline stays machine-local.
6. CLI free-text secrets cannot be reliably scrubbed (headers/cookies/JSON
   bodies are redacted; stdout/stderr are not).
7. Cookie value-level changes hidden by default redaction
   (`redaction.secrets: false` to see them).
8. Re-baselining after edits cannot be distinguished from legitimate use —
   guarded by the skill contract + forced re-baseline warnings.
9. Post-hoc intent detection anchors on check runs (artifact deletion is
   mitigated by report+journal redundancy).
10. No Docker isolation in the benchmark (scrubbed-env LocalExecutor;
    recorded per-run as a SECURITY LIMITATION).

## Key Files to Read First

1. `README.md` — product overview, honest claims
2. `docs/PRD.md` + `docs/ARCHITECTURE.md` (decisions D1–D5)
3. `docs/BEHAVIOR_MODEL.md` — surfaces, capture payloads, category tables
4. `docs/RISK_MODEL.md` — severities, verdict rules, floors
5. `docs/EVALS.md` + `docs/BENCHMARK_DESIGN.md` — validation methodology
6. `docs/FINAL_HOLDOUT_V02/V03/V04.md` — the honest holdout ledgers
7. `docs/CI.md` — the GitHub Action contract
8. `docs/RELEASE.md` — release + PyPI publishing
9. `SKILL.md` — the agent workflow contract (baseline → intent → check)
10. `docs/DEVELOPMENT_LOG.md` — bug history from the V0.1 era
11. `docs/WALKTHROUGH.md` — a complete real-output loop (init → baseline
    → planted regression → BLOCK → intent), good for onboarding users
