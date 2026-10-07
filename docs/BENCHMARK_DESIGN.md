# Real-World GitHub Benchmark — Design

Version: 1.0 (2026-10-05)
Status: Active
Governing principle: **we are trying to falsify Regression Firewall, not to
flatter it.** A real failure discovered here is a success of the benchmark.

---

## 1. Goals

Answer, with reproducible numbers on real open-source projects:

1. How many planted behavioral regressions does Regression Firewall detect?
2. How many does it miss (false negatives)?
3. How many false positives does it produce (controls + extra findings)?
4. Are severity assignments correct?
5. Are EXPECTED/UNEXPECTED classifications correct?
6. Are PASS/REVIEW/BLOCK verdicts reliable?
7. Is the agent workflow (SKILL.md) actually usable?

Out of scope: anything that requires changing V0.1 surface scope (no
database, JS/TS, performance, browser, queue work may be triggered by
benchmark findings — such findings are recorded as limitations).

## 2. Repository selection rules

- Public GitHub repositories, pinned to a **commit SHA** (never `main`).
- License permitting local testing (MIT/Apache/BSD preferred).
- Setup reasonably simple: `pip install` at most; no paid services, no
  production credentials, no large infrastructure, **no external network at
  probe time** (SQLite OK, Postgres/Redis NOT).
- Behavior must be exercisable by V0.1 surfaces: HTTP endpoints, CLI
  commands, or an importable Python package.
- Small or medium size (clone < ~30 MB; primary source files readable
  enough to author precise mutations).
- Reasonably maintained (commit activity within the last ~2 years).

Every repository entry in `benchmarks/manifest.yaml` records:
`id, repo_url, commit_sha, license, python_version, setup_command,
verify_command, supported_surfaces, project_root (subdirectory),
known_requirements`.

Selection is not allowed to change after the first development run except
by adding an `excluded: true` flag **with a written reason** (never
deletion).

### Holdout split

Repositories are split into **Development** (fixes allowed to be driven by
these results) and **Holdout** (run once after development fixes are done;
never used to tune rules). The split is recorded in the manifest before the
first run. Holdout results reported separately and never iterated on.

## 3. Security model

GitHub third-party code is untrusted. The runner's isolation abstraction:

```
Executor (interface)
├── DockerExecutor   — REQUIRED for production use; NOT AVAILABLE on this
│                      machine (no Docker). Interface defined, implementation
│                      deferred; runner refuses to claim container isolation.
└── LocalExecutor    — used for this benchmark iteration, with mitigations
                       and an explicit SECURITY LIMITATION.
```

LocalExecutor mitigations (best effort, NOT equivalent to containers):

- Repositories cloned into a disposable temp workspace; deleted after run.
- Every child process gets a **scrubbed environment**: only PATH, TEMP/TMP,
  SYSTEMROOT/COMSPEC, proxy variables needed for dependency installation.
  Anything matching `TOKEN|SECRET|KEY|PASSWORD|CREDENTIAL` (plus
  GITHUB_TOKEN, GH_TOKEN, AWS_*, AZURE_*, GOOGLE_*) is removed.
- Hard per-step timeouts (clone 120s, setup 600s, probe 60s, per-case 300s).
- Dependency installation is the only phase with expected network use;
  probes run against local servers/commands only (offline by construction).
- No SSH keys, cloud credentials, or home-directory config are ever mounted
  or referenced; the tool's own artifacts directory lives inside the
  disposable workspace.

**SECURITY LIMITATION (honest):** without Docker there is no filesystem,
process, or network isolation from the host. The runner records
`isolation: "local-scrubbed-env"` in every result and refuses to emit a
`security: containerized` claim. Do not run this benchmark against
adversarial repositories on a developer workstation.

## 4. Corpus & layout

```
benchmarks/
    manifest.yaml          # repos (pinned), mutations, ground truth, split
    runner/
        __init__.py
        __main__.py        # python -m benchmarks.runner
        executor.py        # isolation abstraction
        mutations.py       # mutation application engine
        report.py          # metrics + results writer
    results/
        latest.json
        history/           # timestamped copies
```

Third-party repositories are **never committed** into this project; the
runner clones them at run time into a temp workspace.

## 5. Mutation system

Mutations are ordinary source patches (find/replace, verified — a failed
patch is a `MUTATION_FAILURE`, not a detection result). They modify real
project code, never snapshots. Types (taxonomy IDs):

| # | Type | Surface | Expected class / severity / verdict |
|---|---|---|---|
| 01 | status 401→400 | http | unexpected / high / BLOCK |
| 02 | status 200→500 | http | unexpected / high / BLOCK |
| 03 | JSON field removed | http | unexpected / high / BLOCK |
| 04 | JSON field added | http | uncertain / low / PASS |
| 05 | JSON field type changed | http | unexpected / medium / REVIEW |
| 06 | content-type changed | http | unexpected / medium / REVIEW |
| 07 | meaningful header changed | http | uncertain / low / REVIEW |
| 08 | timestamp-only noise | http | no change / PASS |
| 09 | request-id-only noise | http | no change / PASS |
| 10 | exit 0→1 | cli | unexpected / high / BLOCK |
| 11 | stdout changed | cli | uncertain / low / REVIEW |
| 12 | stderr introduced | cli | uncertain / low / REVIEW |
| 13 | generated file added | cli | uncertain / medium / REVIEW |
| 14 | temp-file-only change | cli | no change / PASS |
| 15 | exported symbol removed | public_api | unexpected / critical / BLOCK |
| 16 | exported symbol added | public_api | uncertain / info / PASS |
| 17 | signature changed | public_api | unexpected / medium / REVIEW |
| 18 | implementation-only change | public_api | no change / PASS |
| 19 | intent: expected rename | http | expected (via intent) / PASS |
| 20 | intent: unexpected status flip | http | unexpected / high / BLOCK |

Types 08/09/14/18 are **noise/controls inside the taxonomy**; they exist to
measure false positives from dynamic data and internal-only edits.

### Control cases (per repo where applicable)

- **NO-CHANGE CONTROL**: baseline then check with zero edits → must be
  PASS with zero changes. Primary FPR measurement (run 3× per repo).
- **NON-BEHAVIOR CHANGE CONTROL**: comment/whitespace/internal-variable
  rename patch → must not produce a public behavioral regression
  (`detected: false`). Public API surface: an implementation-only change
  must produce zero symbol/signature changes.

## 6. Ground truth

Authored **before any run** and stored in the manifest. Each case:

```yaml
- id: flaskr_01_status_401_to_400
  type: status_401_to_400
  file: auth.py
  find: 'abort(403, ...'
  replace: 'abort(400, ...'
  expected:
    detected: true
    surface: http
    category: status_changed
    classification: unexpected
    severity: high
    verdict: BLOCK
  intent: null          # or an intent dict for types 19/20
```

Ground truth is never edited after the first run. If reality disagrees
with ground truth, that is a benchmark FINDING (or, for authoring mistakes
like a wrong find-string, a `MUTATION_FAILURE` — the find-string may be
fixed, the expectation may not).

### Matching semantics (real repos produce cascading diffs)

- Every `expected` entry must be found among detected changes (recall).
- Extra detected changes are recorded verbatim and triaged in the report
  as `consequence` (direct mechanical result of the mutation, e.g. the
  response body changing alongside a status flip) or `false_positive`.
  FPR is therefore measured on: controls (strict: zero extra changes) +
  triaged extras on mutation cases. The triage is written down per extra.
- Severity/classification/verdict accuracy compare ground truth against
  the matching entry.

## 7. Metrics (computed by the runner, never hand-written)

repositories, pinned_commits, total_cases, valid_cases (ran to verdict),
detected_regressions, missed_regressions, true_positives,
false_negatives, false_positives (controls + triaged extras),
detection_recall = TP/(TP+FN), false_positive_rate = FP/(FP+TP) across
control+mutation runs, severity_accuracy, classification_accuracy,
verdict_accuracy. Cases that cannot run are classified, never silently
dropped.

## 8. Result classification (per case)

| Class | Meaning |
|---|---|
| BENCHMARK_PASS | ran, matched ground truth |
| REGRESSION_FIREWALL_FAILURE | ran, tool result ≠ ground truth (finding!) |
| REPOSITORY_SETUP_FAILURE | repo install/verify failed (not the tool's fault) |
| INFRASTRUCTURE_FAILURE | clone/network/disk/tooling failed |
| MUTATION_FAILURE | patch did not apply (authoring error) |
| TIMEOUT | any step exceeded its budget |

## 9. Failure analysis rule

Every `REGRESSION_FIREWALL_FAILURE` and every false positive gets a written
root-cause line classified as `CORE_BUG`, `PROBE_COVERAGE_LIMITATION`,
`UNSUPPORTED`, or `BENCHMARK_ERROR`. Only `CORE_BUG` items (within V0.1
scope) get fixes + regression tests; the rest become documented limitations.
The stop condition: a critical security issue, high false-positive rate, a
core false negative, or a baseline-trust failure pauses the benchmark until
fixed and the Development benchmark is re-run.

## 10. Agent dogfooding methodology

After the mutation benchmark: at least 5 real coding-agent tasks on a
benchmark repository, following SKILL.md verbatim (baseline → intent →
edit → check → honor verdict). Executor: ZCode itself (the only coding
agent available in this environment) — recorded as **self-dogfooding with
its inherent bias** (the author wrote SKILL.md and executes it); a truly
independent agent run is future work. Observed and logged: whether the
agent baselines first, writes intent, honors BLOCK, and — critically —
whether it attempts to re-baseline, widen ignores, disable surfaces, raise
thresholds, or mislabel unexpected changes as expected. Skill UX problems
result in SKILL.md edits first, CLI changes never.

## 11. Reproducibility

- Every repo pinned by SHA; results record the tool version, commit SHAs,
  Python version, OS, and the manifest hash.
- `python -m benchmarks.runner --repo <id>` re-runs one repo; no flags
  exist to skip failures, widen ignores, or adjust thresholds mid-run.
- `benchmarks/results/latest.json` plus `history/<timestamp>.json` are
  written every run; `docs/BENCHMARK_RESULTS.md` is generated from JSON
  (the numbers in the doc are computed, not typed).
