# V0.1 Final Evidence Report

**Frozen implementation commit:** `8428a5b13cdd9d54807ee17a23ddbaef61173454`
**Report date:** 2026-10-07
**Tool version:** 0.1.0

> **Update (2026-10-07, release-blocker closure):** the holdout and
> validation findings below were re-diagnosed and fixed the same day (see
> §4 and `docs/RELEASE_BLOCKER_CLOSURE.md`). Original results are preserved
> as the frozen record; post-fix validation is labelled as such.

---

## 1. Bundled Eval Results

| Metric | Value |
|---|---|
| Cases | 20 |
| Passed | 20/20 |
| Detection recall | 100% |
| False positive rate | 0% |
| Severity accuracy | 100% |
| Verdict accuracy | 100% |

## 2. Validation Corpus (8 repos, 66 cases)

Previous holdout repos (typer, httpie, pip-tools) have been reclassified
as validation after being examined during development. All repos now serve
as the validation corpus.

### Development + Validation results (release-blocker closure re-run, 2026-10-07)

| Metric | Value |
|---|---|
| Repositories | 8 |
| Cases total | 66 |
| Planted regressions | 29 |
| Detected regressions | **29** |
| Missed regressions | **0** |
| False positives | **0** |
| Detection recall | **100%** |
| False positive rate | **0%** |
| Severity accuracy | **100%** |
| Verdict accuracy | **100%** |

The earlier 93.10%-recall figure and the failures behind it were
re-diagnosed during the release-blocker closure phase (see §4 and
`docs/RELEASE_BLOCKER_CLOSURE.md`) and the corpus was re-run clean. The
historical numbers remain in `docs/DEVELOPMENT_LOG.md`.

### Validation findings

| Finding | Classification |
|---|---|
| typer.Typer signature FP on every case | **CORE_BUG — FIXED** (canonical signature fingerprint) |
| typer_13 indentation error | **BENCHMARK_ERROR — FIXED** |
| pip_tools_11 command name mutation | **BENCHMARK_ERROR — FIXED** |
| sherlock_13 file_created gap | **PROBE_COVERAGE_LIMITATION** |
| pip_tools_11 stdout not detected | **BENCHMARK_ERROR — FIXED** (probe changed to --help) |

## 3. Historical Regressions

| Case | Surface | Detected | Classification |
|---|---|---|---|
| click format_filename removal | public_api | ✓ | Detected |
| healthchecks status type change | http | ✓ | Detected |
| requests URL encoding change | public_api | ✗ | PROBE_COVERAGE_LIMITATION |
| pip-tools strip-extras change | cli (files) | ✗ | PROBE_COVERAGE_LIMITATION |
| httpie auth-type validation change | cli | ✗ | PROBE_COVERAGE_LIMITATION |

**2/5 detected, 3/5 PROBE_COVERAGE_LIMITATION.**

The 3 missed cases are real regressions that the tool CAN detect, but only
if the user configures probes that exercise the affected behavior. The tool
cannot detect behavior it has no probes for. This is a fundamental design
limitation, not a bug.

See `docs/HISTORICAL_REGRESSIONS.md` for full details.

## 4. Fresh Final Holdout

The holdout was run once on 2026-10-07 (original results below, preserved as
the frozen record). It is now **consumed**: issues found were fixed the same
day, so per its rules this corpus moves to the validation corpus and a new
fresh holdout must be selected before the next release cycle. Selection
record + post-fix notes: `docs/FINAL_HOLDOUT.md`.

| Repo | URL | Commit | License | Surface | Cases | Original result |
|---|---|---|---|---|---|---|
| bottle | [bottlepy/bottle](https://github.com/bottlepy/bottle) | `cbd569c447` | MIT | public_api | 5 | **5/5 PASS** |
| urllib3 | [urllib3/urllib3](https://github.com/urllib3/urllib3) | `a164d79c8c` | Apache-2.0 | public_api | 5 | 4/5 (3 symbol cases missed) |
| packaging | [pypa/packaging](https://github.com/pypa/packaging) | `2aada00b15` | Apache-2.0/BSD | public_api | 5 | REPOSITORY_SETUP_FAILURE |

### Holdout findings → corrected root cause (re-diagnosed 2026-10-07)

The originally recorded "src-layout editable install" diagnosis was **wrong**.
Controlled reproduction found two compounding issues plus one probe-config
gap:

| Finding | Corrected root cause | Classification | Status |
|---|---|---|---|
| urllib3 symbol mutations missed | (1) The benchmark's per-case restore (`git clean -fdqx`) deleted the build-generated `src/urllib3/_version.py`; every capture after that failed. (2) A probe failing on BOTH sides produced no diff and read as a silent PASS — the tool had no "no evidence" guard. The original signature mutation was also invalid (inserted a second `*` → SyntaxError). | `BENCHMARK_ERROR` + `CORE_BUG` | **FIXED** — runner re-applies setup per case; no-evidence guard keeps REVIEW and warns "NOT verified"; mutation corrected for post-fix validation |
| packaging setup failure | The stored holdout manifest wrote `setup_commands` as a plain string; the runner iterated it character-by-character into `python -` (empty stdin → exit 0 → silent no-install). Bottle only survived because it is a single file at the repo root. | `BENCHMARK_ERROR` | **FIXED** — argv lists; the runner rejects string commands loudly |
| packaging mutations missed (after setup fix) | The probes covered only the top-level `packaging` module while the mutations edit `packaging.version`. | `BENCHMARK_ERROR` | **FIXED** — missing probe added |

### Post-fix validation (NOT a holdout result)

After the fixes: **bottle 7/7, urllib3 7/7, packaging 7/7 — 3/3 planted
regressions detected per repo, 0 false positives.** These numbers are
post-fix validation and must not be cited as holdout results.

## 5. Independent Agent Validation

**Status: EXECUTED — 2026-10-07** (fresh-context DeepSeek V4 Pro session in
OpenCode; no access to this protocol, the benchmark design, mutations, or
ground truth). Result: **10/10 protocol tasks, 0 hard-rule violations, 3/3
check-silencing pressures survived.** Full record:
`docs/INDEPENDENT_AGENT_VALIDATION.md`; raw evidence:
`docs/evidence/agent-validation-2026-10-07/`.

Scope (do not overstate): one same-machine agent run on two repositories
(Flask tutorial app; Sherlock CLI). Stronger than self-dogfooding, not a
cross-vendor field trial. Findings recorded there (post-check intent
additions, public-API intent-target discoverability, API-probing deployment);
the intent-audit P0 hardening below closes the main observed weakness.

## 6. Core bugs found by real-world testing (all fixed + regression tests)

| # | Bug | Fix | Regression test |
|---|---|---|---|
| 1 | `capture/http.py` shadowed stdlib `http` | Renamed to `http_probe.py` | `test_api_runner_does_not_shadow_stdlib_http` |
| 2 | CORS header order FP | Set-semantic normalization | `test_cors_headers_order_insensitive` |
| 3 | Float epoch strings not masked | Float-aware epoch check | `test_float_epoch_string_with_temporal_key` |
| 4 | Intent path bracket indices | Bracket-to-dot normalization | `test_intent_path_bracket_indices_normalized` |
| 5 | `{port}` not substituted in server args | Substitution covers all command parts | dev benchmark healthchecks |
| 6 | `inspect.signature()` nondeterministic for framework callables | Canonical structural fingerprint | `test_canonical_signature_deterministic_across_subprocesses` |
| 7 | `git clean` without `-x` leaves .gitignore-matched files | `-x` flag added | dev benchmark sherlock_13 |
| 8 | Probe failing on both sides read as silent PASS (no evidence) | No-evidence guard: REVIEW + "NOT verified" warning | `test_unverifiable_probe_cannot_pass` |
| 9 | Public-API capture could not resolve standard src-layout projects | `src/` import root; stale `__all__` names classified as removals; module-dict enumeration behind restrictive `__dir__` | `test_src_layout_api.py` (7), `test_api_runner_sees_names_hidden_by_dunder_dir` |
| 10 | An observed change could be reclassified as EXPECTED by a late intent edit | Intent audit trail + post-hoc guard (`--accept-post-hoc-intent`); append-only journal as report redundancy | `test_intent_audit.py` (7) + `test_intent_audit_states.py` (5) |
| 11 | Benchmark setup commands written as strings silently no-op'd (char-split → `python -`) | Manifest argv lists + loud runner error | post-fix holdout re-run |

## 7. Known limitations

1. **No Docker isolation** — LocalExecutor with scrubbed env only
2. **Public API signatures** — the canonical fingerprint captures structure
   but not default VALUES; `inspect.signature` can still be nondeterministic
   for some framework-generated callables
3. **Post-hoc intent detection anchors on check runs** — the tool cannot
   observe when code was actually edited, so intent written before the first
   check of a baseline window counts as pre-implementation. Deleting tool
   artifacts to hide evidence is forbidden by the skill and mitigated
   (report + journal redundancy; baseline integrity hash)
4. **CLI generated-file timing** — file capture may race with process exit
   for some CLI probes (PROBE_COVERAGE_LIMITATION)
5. **Independent agent validation was a single same-machine run** (DeepSeek
   in OpenCode); no cross-vendor field trial yet
6. **The fresh holdout is consumed** — post-fix validation passed 7/7 per
   repo, but a NEW fresh holdout must be selected before the next release
7. **Public API behavioral changes** — the tool detects symbol/signature
   changes but NOT behavioral changes within method bodies
   (HR-03 requests URL encoding)
8. **No FastAPI app in corpus** — no small self-contained FastAPI app met
   selection criteria
9. **Module-level imported helpers count as public namespace** — e.g.
   removing a module-level `import typing` is reported as a symbol removal;
   consistent with `dir()` semantics, but can be noisy in refactors

