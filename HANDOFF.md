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
| pytest | **236 passed / 0 failed** |
| Bundled evals | **21/21** (recall 100%, FPR 0%, verdict 100%) |
| Real-world benchmark | 8 repos, 66 cases, 4 core bugs found & fixed (V0.1 code) |
| Independent agent validation | **10/10 tasks, 0 hard-rule violations** (DeepSeek V4 Pro / OpenCode, 2026-10-07, V0.1 code) |

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
| New fresh holdout | HIGH (before the release AFTER v0.2.0, or a v0.2.x detection change) | The 2026-10-07 holdout corpus is consumed. V0.2 touched capture (cli dirs) and normalization (custom rules) — both are additive and covered by tests + eval case 21, but a real-repo benchmark run on V0.2 code has not happened yet. Select 3 NEW repos (never in the 11 used) before the next release cycle. |
| PyPI publication | MEDIUM | Everything is prepared: `publish.yml` (manual, OIDC Trusted Publisher) + `docs/RELEASE.md`. BLOCKED on the repo owner doing the one-time PyPI side: add the pending trusted publisher (owner=Tong-bit-art, repo=regression-firewall, workflow=publish.yml, env=pypi) and create the `pypi` environment in repo settings. Then tag a release and run the workflow. |
| CI maintenance | LOW | **DONE 2026-10-25**: checkout@v5, setup-python@v6. |
| typer.Typer signature: full fix | LOW | Canonical fingerprint works for most cases; edge cases with rich-conditional imports still UNSUPPORTED |
| Cross-vendor agent validation on V0.2 | LOW | Independent agent validation ran on V0.1 (2026-10-07); repeat on V0.2 with a different vendor when convenient. |

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
