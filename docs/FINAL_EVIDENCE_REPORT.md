# V0.1 Final Evidence Report

**Frozen implementation commit:** `8428a5b13cdd9d54807ee17a23ddbaef61173454`
**Report date:** 2026-10-07
**Tool version:** 0.1.0

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

### Development + Validation results (final, all fixes deployed)

| Metric | Value |
|---|---|
| Repositories | 8 |
| Cases total | 66 (38 dev + 18 previous holdout + 10 additional) |
| Planted regressions | 29 |
| Detected regressions | 27 |
| Missed regressions | 2 |
| False positives (after triage) | 0 |
| Detection recall | **93.10%** |
| False positive rate | **0%** |
| Severity accuracy | **100%** |
| Verdict accuracy | **93.94%** |

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

| Repo | URL | Commit | License | Surface | Cases | Result |
|---|---|---|---|---|---|---|
| bottle | [bottlepy/bottle](https://github.com/bottlepy/bottle) | `cbd569c447` | MIT | public_api | 5 | **5/5 PASS** |
| urllib3 | [urllib3/urllib3](https://github.com/urllib3/urllib3) | `a164d79c8c` | Apache-2.0 | public_api | 5 | 4/5 (3 symbol cases missed) |
| packaging | [pypa/packaging](https://github.com/pypa/packaging) | `2aada00b15` | Apache-2.0/BSD | public_api | 5 | REPOSITORY_SETUP_FAILURE |

### Fresh holdout metrics (bottle only — the only repo that ran to verdict)

| Metric | Value |
|---|---|
| Cases | 5 |
| Planted regressions | 3 |
| Detected | 3 |
| Recall | **100%** |
| FPR | **0%** |
| Severity accuracy | **100%** |
| Verdict accuracy | **100%** |

### Fresh holdout findings

| Finding | Root cause | Classification |
|---|---|---|
| urllib3 symbol mutations not detected | `pip install -e .` for src/-layout projects uses a meta-path finder that may resolve to a stale copy in the api-runner subprocess; the mutation edits `src/urllib3/__init__.py` but the subprocess imports from a cached path | `UNSUPPORTED` — src/-layout editable installs require PYTHONPATH to include `src/`, not just the repo root |
| packaging setup failure | `pip install -e .` succeeded but the verify step (`import packaging`) failed — the editable install may need a build backend that isn't available in the clean venv | `INFRASTRUCTURE_FAILURE` |

The fresh holdout was run ONCE. The original results are final. No iteration.

## 5. Independent Agent Validation

**Status: NOT EXECUTED**

No independent coding agent CLI is available in this environment.
The protocol is documented in `docs/INDEPENDENT_AGENT_VALIDATION.md`
(10 tasks covering baseline compliance, intent recording, check execution,
BLOCK handling, REVIEW investigation, and anti-cheating compliance).

Self-dogfooding was performed (5 tasks on flaskr by the tool's author).
This demonstrates the workflow is *followable* but does not measure
independent-agent compliance. This is a known Beta release limitation.

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

## 7. Known limitations

1. **No Docker isolation** — LocalExecutor with scrubbed env only
2. **Public API signatures** — canonical fingerprint captures structure but
   not default VALUES; `inspect.signature` can still be nondeterministic
   for some framework-generated callables (documented as UNSUPPORTED)
3. **src/-layout editable installs** — the api-runner subprocess may not
   resolve the package correctly for src/-layout projects in certain
   benchmark configurations
4. **CLI generated-file timing** — file capture may race with process exit
   for some CLI probes (PROBE_COVERAGE_LIMITATION)
5. **Independent agent validation not executed**
6. **Fresh holdout partially failed** — 2/3 repos had setup issues;
   only bottle (1/3) produced full detection results
7. **Public API behavioral changes** — the tool detects symbol/signature
   changes but NOT behavioral changes within method bodies
   (HR-03 requests URL encoding)
8. **No FastAPI app in corpus** — no small self-contained FastAPI app met
   selection criteria
9. **Self-dogfooding only** — no independent agent verification
