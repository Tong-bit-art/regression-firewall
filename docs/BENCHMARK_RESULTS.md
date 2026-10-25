# Real-World Benchmark Results

*Generated 2026-10-25T14:04:31Z by regression-firewall 0.2.0. Numbers are computed from benchmarks/results/latest.json — see docs/BENCHMARK_DESIGN.md for methodology.*

- Isolation: `local-scrubbed-env` (**SECURITY LIMITATION**: no container isolation available on this machine — scrubbed-environment local execution only)
- Repositories: 3 (pinned commits)
- Manifest hash: `5573c51e21f7`

## Metrics

| Metric | Value |
|---|---|
| cases_total | 21 |
| cases_ran_to_verdict | 21 |
| repository_setup_failures | 0 |
| infrastructure_failures | 0 |
| mutation_failures | 0 |
| timeouts | 0 |
| planted_regression_cases | 9 |
| detected_regressions | 9 |
| missed_regressions | 0 |
| false_positives | 0 |
| noise_or_control_cases | 12 |
| noise_or_control_clean | 12 |
| detection_recall | 1.0 |
| false_positive_rate | 0.0 |
| severity_accuracy | 1.0 |
| verdict_accuracy | 1.0 |

## Case detail

| Repo | Case | Type | Class | Verdict (expected → detected) |
|---|---|---|---|---|
| zod | zod_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| zod | zod_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| zod | zod_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| zod | zod_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| zod | zod_15_symbol_removed | symbol_removed | BENCHMARK_PASS | BLOCK → BLOCK |
| zod | zod_17_signature_changed | signature_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| zod | zod_16_symbol_added | symbol_added | BENCHMARK_PASS | PASS → PASS |
| isort | isort_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| isort | isort_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| isort | isort_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| isort | isort_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| isort | isort_10_exit_0_to_1 | exit_0_to_1 | BENCHMARK_PASS | BLOCK → BLOCK |
| isort | isort_11_stdout_changed | stdout_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| isort | isort_13_fs_write_added | generated_file_added | BENCHMARK_PASS | REVIEW → REVIEW |
| dateutil | du_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| dateutil | du_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| dateutil | du_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| dateutil | du_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| dateutil | du_15_symbol_removed | symbol_removed | BENCHMARK_PASS | BLOCK → BLOCK |
| dateutil | du_17_signature_changed | signature_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| dateutil | du_16_symbol_added | symbol_added | BENCHMARK_PASS | PASS → PASS |

## Findings (REGRESSION_FIREWALL_FAILURE cases)

None in this run.

FRESH HOLDOUT V0.3 — repos disjoint from all prior development/validation.
Frozen tool: main @ ed0a7e2 (post-V0.3). First run 2026-10-25, Windows 11, Python 3.11.9.
No HTTP surface; discovery covered by integration tests (see header).
SECURITY LIMITATION: no Docker; LocalExecutor with scrubbed env (see docs/BENCHMARK_DESIGN.md).
