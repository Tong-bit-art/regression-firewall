# Real-World Benchmark Results

*Generated 2026-10-07T03:42:34Z by regression-firewall 0.1.0. Numbers are computed from benchmarks/results/latest.json — see docs/BENCHMARK_DESIGN.md for methodology.*

- Isolation: `local-scrubbed-env` (**SECURITY LIMITATION**: no container isolation available on this machine — scrubbed-environment local execution only)
- Repositories: 3 (pinned commits)
- Manifest hash: `553a5b7ad4a2`

## Metrics

| Metric | Value |
|---|---|
| cases_total | 18 |
| cases_ran_to_verdict | 18 |
| repository_setup_failures | 0 |
| infrastructure_failures | 0 |
| mutation_failures | 0 |
| timeouts | 0 |
| planted_regression_cases | 6 |
| detected_regressions | 4 |
| missed_regressions | 2 |
| false_positives | 0 |
| noise_or_control_cases | 12 |
| noise_or_control_clean | 12 |
| detection_recall | 0.6667 |
| false_positive_rate | 0.0 |
| severity_accuracy | 1.0 |
| verdict_accuracy | 0.8889 |

## Case detail

| Repo | Case | Type | Class | Verdict (expected → detected) |
|---|---|---|---|---|
| typer | typer_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| typer | typer_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| typer | typer_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| typer | typer_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| typer | typer_15_symbol_removed | symbol_removed | BENCHMARK_PASS | BLOCK → BLOCK |
| typer | typer_16_symbol_added | symbol_added | BENCHMARK_PASS | PASS → PASS |
| typer | typer_13_generated_file | generated_file_added | REGRESSION_FIREWALL_FAILURE | REVIEW → PASS |
| httpie | httpie_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| httpie | httpie_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| httpie | httpie_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| httpie | httpie_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| httpie | httpie_12_stderr_introduced | stderr_introduced | BENCHMARK_PASS | REVIEW → REVIEW |
| httpie | httpie_13_generated_file | generated_file_added | REGRESSION_FIREWALL_FAILURE | REVIEW → PASS |
| pip-tools | pip_tools_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| pip-tools | pip_tools_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| pip-tools | pip_tools_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| pip-tools | pip_tools_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| pip-tools | pip_tools_11_stdout_changed | stdout_changed | BENCHMARK_PASS | REVIEW → REVIEW |

## Findings (REGRESSION_FIREWALL_FAILURE cases)

- **typer/typer_13_generated_file** (generated_file_added): missing=['cli/file_created/uncertain/medium']; extras=none
- **httpie/httpie_13_generated_file** (generated_file_added): missing=['cli/file_created/uncertain/medium']; extras=none

SECURITY LIMITATION: no Docker on this machine; LocalExecutor with a
scrubbed environment is used and recorded per-run. See BENCHMARK_DESIGN.md.
FastAPI-app exclusion: no small self-contained offline-runnable FastAPI
application met the selection criteria this round; the HTTP surface is
covered by two real WSGI apps (flaskr, healthchecks) instead.
healthchecks runs on Python 3.14 (Django 6.1 requires >= 3.12); the
venv_command override below is machine-specific and documented here.
