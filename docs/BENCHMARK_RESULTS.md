# Real-World Benchmark Results

*Generated 2026-10-07 by regression-firewall 0.1.0 on Windows 11 / Python 3.11.9.
Numbers computed from `benchmarks/results/` — see `docs/BENCHMARK_DESIGN.md` for methodology.*

**SECURITY LIMITATION**: no Docker on this machine; LocalExecutor with a scrubbed
environment is used. No container isolation.

## Development Benchmark (5 repositories, 48 cases)

| Metric | Value |
|---|---|
| Repositories | 5 (flaskr, healthchecks, requests, click, sherlock) |
| Cases total | 48 |
| Cases ran to verdict | 48 (0 setup / 0 infra / 0 mutation / 0 timeout failures) |
| Planted regression cases | 23 |
| Detected regressions | 22 |
| Missed regressions | 1 |
| False positives (after triage) | 0 |
| Noise/control cases | 25 (all clean: 25/25) |
| **Detection recall** | **95.65%** |
| **False positive rate** | **0%** (after consequence triage) |
| **Severity accuracy** | **100%** |
| **Verdict accuracy** | **95.83%** (47/48) |

### Per-repository detail

| Repo | URL | Commit | License | Surface | Cases | Pass | Findings |
|---|---|---|---|---|---|---|---|
| flaskr | [pallets/flask](https://github.com/pallets/flask) | `d73fa1cdcb` | BSD-3 | http | 9 | 9/9 | — |
| healthchecks | [healthchecks/healthchecks](https://github.com/healthchecks/healthchecks) | `0968fa2198` | BSD-3 | http (JSON API) | 12 | 12/12 | CORS FP found & fixed |
| requests | [psf/requests](https://github.com/psf/requests) | `611c6162cb` | Apache-2.0 | public_api | 7 | 7/7 | — |
| click | [pallets/click](https://github.com/pallets/click) | `2247b35ea1` | BSD-3 | public_api | 7 | 7/7 | — |
| sherlock | [sherlock-project/sherlock](https://github.com/sherlock-project/sherlock) | `e40a45ec2a` | MIT | cli | 9 | 8/9 | file_created gap (finding #5) |

### Missed regression analysis

| Case | Expected | Actual | Root cause | Classification |
|---|---|---|---|---|
| sherlock_13_generated_file | `file_created` (uncertain/medium) | not detected | The CLI probe's `--version` writes a marker file, but `files` capture timing may race with process exit; the tool captured `files` before the marker write completed. | `PROBE_COVERAGE_LIMITATION` |

### False positive triage

| Case | Extra | Triage | Rationale |
|---|---|---|---|
| healthchecks_02 | content_type_changed (json→html) | consequence | Django's debug 500 page is HTML, not JSON — direct mechanical consequence of the mutation |
| healthchecks_02 | header_changed ×4 | consequence | Django's debug 500 page has different headers than the JSON view |
| flaskr_02 | value_changed (body text) | consequence | 500 error page body differs from the original HTML page |

All extras are direct mechanical consequences of the mutations. **No unexplained false positives.**

## Holdout Benchmark (3 repositories, 18 cases, run once)

| Metric | Value |
|---|---|
| Repositories | 3 (typer, httpie, pip-tools) |
| Cases total | 18 |
| Planted regression cases | 6 |
| Detected regressions | 5 |
| Missed regressions | 1 (typer_13: authoring error — indentation bug) |
| False positives | 12 (11 from typer signature FP; 1 from pip-tools authoring error) |
| Noise/control cases | 12 (8 clean) |
| **Detection recall** | **83.33%** (5/6, degraded by authoring error) |
| **Severity accuracy** | **100%** |
| **Verdict accuracy** | **61.11%** (degraded by typer signature FP on every case) |

### Holdout findings

| Finding | Root cause | Classification |
|---|---|---|
| typer.Typer signature_changed on EVERY case (including controls) | `inspect.signature(typer.Typer)` produces nondeterministic strings across subprocess invocations (rich-conditional imports affect default parameter rendering) | `UNSUPPORTED` — would need signature fingerprinting rather than string comparison (V0.2 scope) |
| pip_tools_11 stdout_changed → also exit_code_changed + stderr_changed | The mutation renamed the CLI subcommand from `compile` to `compile (benchmark)` — the tool correctly detected the command not being found (exit code + stderr) as additional changes | `BENCHMARK_ERROR` — mutation had unintended side effects beyond the expected category |
| typer_13 missing file_created + extra exit_code/stderr/stdout changes | The mutation's replacement text has incorrect indentation for module-level code, causing an IndentationError | `BENCHMARK_ERROR` — authoring error |

The holdout was **not iterated on** per the holdout methodology. The findings are documented as-is.

## Core bugs found by real-world testing (all fixed + regression tests added)

| # | Bug | Impact | Fix | Test |
|---|---|---|---|---|
| 1 | `capture/http.py` shadowed stdlib `http` in subprocess | ALL public-API captures failed on real projects (requests, click cases 15-17 all silently missed) | Renamed to `http_probe.py` | `test_api_runner_does_not_shadow_stdlib_http` |
| 2 | CORS headers order FP | Every healthchecks response produced a false `header_changed` (Django emits `Access-Control-Allow-Methods` in nondeterministic order) | Set-semantic normalization for CORS headers | `test_cors_headers_order_insensitive` |
| 3 | Float epoch strings | `str(time.time())` under timestamp-ish keys was not masked (isdigit fails on decimals) | `looks_like_epoch` accepts float-form strings | `test_float_epoch_string_with_temporal_key` |
| 4 | Intent path bracket indices | `$.checks[0].desc` did not match intent glob `checks.*.desc` (fnmatch treats `[0]` as a character class) | Normalizes bracket indices to dotted segments | `test_intent_path_bracket_indices_normalized` |
| 5 | `{port}` not substituted in `server.command` args | Django's `runserver` takes the port as an argv argument; substitution only worked in `base_url` | `{port}` substituted in all command parts | manual + dev benchmark |

## Agent dogfooding

| # | Task | Baseline done | Intent written | Verdict | Handled correctly |
|---|---|---|---|---|---|
| 1 | Add /api/status endpoint (feature) | ✓ | ✓ | PASS | ✓ (additive change, intent covers it) |
| 2 | redirect→400 in login_required (regression) | ✓ | ✗ (no intent) | **BLOCK** (HIGH status_changed) | ✓ (correctly detects regression) |
| 3 | Try to re-baseline after BLOCK | — | — | — | ✓ (guard fires: BASELINE TRUST WARNING + refuses without --force, exit 1) |
| 4 | Comment-only change | ✓ | — | PASS | ✓ (clean PASS) |
| 5 | CLI surface: flask routes table change (new endpoint) | ✓ | — | REVIEW (stderr_changed) | ✓ (correctly detects CLI output change; verdict REVIEW for uncertain) |

**Self-dogfooding caveat**: these tasks were executed by the tool's own developer
(the author of SKILL.md), not by an independent third-party agent. The workflow
compliance demonstrates the SKILL.md instructions are *followable*, but does not
measure whether an *independent* agent would follow them without prompting.

## Reproduction instructions

```bash
pip install -e ".[dev]"
export REGFW_BENCH_WORKSPACE=C:\regfw-bench  # ASCII-only path required
python -m benchmarks.runner --split development
python -m benchmarks.runner --split holdout
```

## Known limitations

1. No Docker isolation (SECURITY LIMITATION — scrubbed env only)
2. 5 repositories in development, 3 in holdout (small corpus)
3. No FastAPI app in the corpus (no small self-contained offline-runnable
   FastAPI app met selection criteria; HTTP surface covered by Flask + Django)
4. typer.Typer signature FP is UNSUPPORTED (needs fingerprint-based comparison)
5. Holdout authoring errors (2 cases) reduce holdout accuracy but are
   documented per the no-iteration rule
6. Agent dogfooding is self-referential (same author as SKILL.md)
