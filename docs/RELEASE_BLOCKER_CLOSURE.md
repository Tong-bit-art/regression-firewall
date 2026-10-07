# V0.1 Release Blocker Closure Report

**Date:** 2026-10-07
**Scope:** close the known issues affecting V0.1 beta credibility. Feature
freeze respected: no new behavior surfaces, no V0.2 work.

## Gate summary

| Gate | Result |
|---|---|
| src-layout public API coverage | **FIXED** |
| Intent audit immutability | **FIXED** |
| Tests (pytest) | **176 passed** |
| Bundled evals | **20/20** (recall 100%, FPR 0%, severity/verdict 100%) |
| Validation corpus | **66/66 cases ran, 29/29 planted regressions detected, 0 false positives** |
| Fresh holdout (post-fix validation, not holdout numbers) | **7/7 per repo** — bottle, urllib3, packaging (3/3 planted each, 0 FP) |
| CI (GitHub Actions) | **7/7 green** (Ubuntu 3.11–3.13, Windows/macOS 3.12–3.13) |
| Independent agent evidence | **10/10 protocol tasks, 0 hard-rule violations, 3/3 pressures survived** |

**Final verdicts**

- **ENGINEERING READY: YES**
- **INDEPENDENT AGENT VALIDATED: YES (with caveats)**
- **PUBLIC BETA RELEASE READY: YES**

## 1. src-layout public API coverage — FIXED

The previously recorded "src/-layout editable install" diagnosis was wrong.
Controlled reproduction (editable install + direct api-runner runs + a real
benchmark re-run) found the actual chain:

1. The benchmark's per-case restore (`git clean -fdqx`) deleted
   build-generated files (urllib3's `src/urllib3/_version.py`), so every
   capture after setup failed.
2. A probe failing at **both** baseline and check produced no diff and
   silently read as PASS — no evidence was being reported as no change.
3. `packaging` mutations target `packaging.version`, but the probed module
   was only the top-level `packaging` (BENCHMARK_ERROR).
4. The stored holdout manifest wrote `setup_commands` as a plain string; the
   runner iterated it character-by-character into `python -` (empty stdin →
   exit 0 → silent no-install). Bottle only survived because it is a single
   file at the repository root.
5. The urllib3 signature mutation inserted a second `*` into the signature
   → SyntaxError (invalid code; BENCHMARK_ERROR).

Fixes (no repository-specific special-casing):

- **Import roots:** the introspection subprocess adds the project's own
  `src/` root (standard src-layout) alongside the project root.
- **Correct classification:** names declared in `__all__` that can no longer
  be resolved are reported as `symbol_removed` (previously misreported as a
  signature change); symbol enumeration uses the module namespace, so
  modules with a restrictive `__dir__` (`packaging.version`) no longer hide
  importable symbols; unresolvable-before/resolvable-after is reported as
  `symbol_added`.
- **No-evidence guard:** a probe that fails at both baseline and check keeps
  the verdict at REVIEW and the report says the probe was **NOT verified**;
  failed captures are warned about at capture time.
- **Benchmark runner:** argv-list validation for `setup_commands` /
  `verify_command` / `api_key_command` (strings fail loudly); setup is
  re-applied after each per-case restore (regenerates build artifacts);
  working tree restored before setup as well as per case; packaging probe
  covers `packaging.version`; the three `*_benchmark_marker.txt`
  `clean_excludes` entries removed (stale outputs leaked across runs and
  made `file_created` undetectable); flaskr case extras that are mechanical
  consequences of the mutation are declared.

Regression coverage: `tests/fixtures/src_layout_package/` +
`tests/integration/test_src_layout_api.py` (7 tests: removal, clean removal,
addition, signature, implementation-only no-op, repeated stability,
discover), `test_api_runner_sees_names_hidden_by_dunder_dir`,
`test_unverifiable_probe_cannot_pass`, new unit tests in
`tests/unit/test_diff_public_api.py`.

Post-fix validation (not a holdout result): **bottle 7/7, urllib3 7/7,
packaging 7/7** — 3/3 planted regressions detected per repo, 0 false
positives. The original holdout results remain the frozen record
(`docs/FINAL_EVIDENCE_REPORT.md` §4); the holdout is now consumed and a new
fresh holdout must be selected before the next release cycle.

## 2. Intent audit immutability — FIXED

The tool now records intent state (content hash, per-entry fingerprints,
baseline id) at baseline time and at every check. An entry that first
appears (or is modified) after a previous check already observed the
behavior is **POST-HOC**:

- marked on the change (`post_hoc: true`) and called out with a
  **POST-HOC INTENT WARNING** in console, Markdown and JSON reports;
- cumulative across checks: re-running `check` does not clear it;
- keeps the verdict at **REVIEW** — a post-hoc entry can never turn the
  check into a clean PASS by itself;
- accepted only with an explicit `check --accept-post-hoc-intent`
  acknowledgement, which is recorded in `intent_audit` (accepted entries no
  longer guard; new late entries guard again);
- an append-only `intent_audit.jsonl` journal keeps the audit alive if
  `report.json` is deleted or rotated, and the anti-rebaseline guard consults
  it too (deleting the report is not a way around the guard).

Tests: `tests/integration/test_intent_audit.py` (7: normal flow, BLOCK →
post-hoc REVIEW, persistence until accepted, modified entry, new-baseline
reset, accept-without-pending, report-deletion bypass) +
`tests/unit/test_intent_audit_states.py` (5 state/compare tests).

Documented limitation: the tool cannot observe when code was actually
edited; the anchor is the previous check run. Intent written before the
first check of a baseline window counts as pre-implementation.

## 3. Independent agent evidence

Executed 2026-10-07 with a fresh-context DeepSeek V4 Pro session in OpenCode
(no access to the protocol, benchmark design, mutations, or ground truth):
10/10 tasks, 0 hard-rule violations, 3/3 check-silencing pressures survived.
Full record + caveats: `docs/INDEPENDENT_AGENT_VALIDATION.md`. This is an
independent agent *instance* on one machine, not a cross-vendor field trial;
claims are scoped accordingly.

## 4. Final verification (as run)

| Check | Result |
|---|---|
| Full pytest | 176 passed |
| Bundled evals (`python -m evals.runner`) | 20/20; recall 100%, FPR 0%, severity/verdict 100% |
| Validation corpus smoke (`python -m benchmarks.runner --split all`) | 66/66 cases, 29/29 planted regressions, 0 FP, 0 setup failures |
| src-layout regression fixture | 7/7 integration tests |
| Independent-agent protocol regression tests | intent audit (12), no-evidence guard, anti-rebaseline, skill hard-rule tests — all passing |
| Intent post-hoc mutation tests | 12 tests (integration + unit), including report-deletion bypass |
| Clean package install | sdist + wheel built and installed into fresh venvs; `--version` ok from both |
| CLI smoke (installed wheel) | discover → baseline → mutate → check (REVIEW, exit 1) → explain |
| Secret redaction tests | passing (`test_snapshot_secrets_redacted`, `test_extended_secret_names_redacted`) |
| Baseline provenance tests | passing (`test_baseline_provenance_recorded`, `…_with_git`, `test_baseline_tamper_detection`) |
| Anti-rebaseline tests | passing (`test_rebaseline_after_block_requires_force_and_warns`, `test_normal_rebaseline_after_pass_does_not_warn`) |
| CI | 7/7 green on `main` |

## 5. Known limitations (documented; not release blockers for beta)

1. No Docker isolation (scrubbed environment only)
2. Post-hoc intent detection anchors on check runs (tool cannot observe code
   edit time); artifact deletion is forbidden by the skill and mitigated
3. CLI free-text secrets cannot be reliably scanned
4. Cookie value-level changes hidden by default redaction
5. ISO date rule masks stable business dates
6. Re-baselining after edits cannot be distinguished from legitimate use
   (guarded by `--force` + persistent trust warning)
7. Public API behavioral changes within method bodies are not detected
8. No FastAPI app in the benchmark corpus
9. Independent validation was a single same-machine agent run; no
   cross-vendor field trial yet
10. Module-level imported helpers count as public namespace (consistent with
    `dir()` semantics; can be noisy in refactors)

## 6. Remaining blockers

**None for the public beta.** Before the next release cycle:

- select a new fresh holdout (the current one is consumed);
- PyPI publication (packaging task, not a blocker);
- non-blocking CI maintenance: Node 20 deprecation warnings for
  `actions/checkout@v4` / `actions/setup-python@v5`, and the `ubuntu-latest`
  → Ubuntu 26 migration on 2026-10-19.

Next step: **public release preparation** (packaging, release notes, PyPI
metadata) — no further V0.1 feature development.
