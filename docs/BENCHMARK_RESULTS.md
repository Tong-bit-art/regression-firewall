# Real-World Benchmark Results

*Generated 2026-10-25T16:40:53Z by regression-firewall 0.3.0. Numbers are computed from benchmarks/results/latest.json — see docs/BENCHMARK_DESIGN.md for methodology.*

- Isolation: `local-scrubbed-env` (**SECURITY LIMITATION**: no container isolation available on this machine — scrubbed-environment local execution only)
- Repositories: 3 (pinned commits)
- Manifest hash: `7f063705e1d3`

## Metrics

| Metric | Value |
|---|---|
| cases_total | 23 |
| cases_ran_to_verdict | 23 |
| repository_setup_failures | 0 |
| infrastructure_failures | 0 |
| mutation_failures | 0 |
| timeouts | 0 |
| planted_regression_cases | 10 |
| detected_regressions | 10 |
| missed_regressions | 0 |
| false_positives | 0 |
| noise_or_control_cases | 13 |
| noise_or_control_clean | 13 |
| detection_recall | 1.0 |
| false_positive_rate | 0.0 |
| severity_accuracy | 1.0 |
| verdict_accuracy | 1.0 |

## Case detail

| Repo | Case | Type | Class | Verdict (expected → detected) |
|---|---|---|---|---|
| datasette | ds_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| datasette | ds_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| datasette | ds_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| datasette | ds_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| datasette | ds_10_exit_0_to_1 | exit_0_to_1 | BENCHMARK_PASS | BLOCK → BLOCK |
| datasette | ds_11_stdout_changed | stdout_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| datasette | ds_sqlite_query_added | db_query_added | BENCHMARK_PASS | REVIEW → REVIEW |
| datasette | ds_perf_slowdown | runtime_regressed | BENCHMARK_PASS | REVIEW → REVIEW |
| datasette | ds_select_touch_package | stdout_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| datasette | ds_select_untouched | no_change_control | BENCHMARK_PASS | REVIEW → REVIEW |
| pluggy | pg_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| pluggy | pg_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| pluggy | pg_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| pluggy | pg_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| pluggy | pg_15_symbol_removed | symbol_removed | BENCHMARK_PASS | BLOCK → BLOCK |
| pluggy | pg_16_symbol_added | symbol_added | BENCHMARK_PASS | REVIEW → REVIEW |
| more-itertools | mi_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| more-itertools | mi_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| more-itertools | mi_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| more-itertools | mi_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| more-itertools | mi_15_symbol_removed | symbol_removed | BENCHMARK_PASS | BLOCK → BLOCK |
| more-itertools | mi_17_signature_changed | signature_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| more-itertools | mi_16_symbol_added | symbol_added | BENCHMARK_PASS | PASS → PASS |

## Findings (REGRESSION_FIREWALL_FAILURE cases)

None in this run.

FRESH HOLDOUT V0.4 — repos disjoint from all prior development/validation.
Frozen tool: main @ 047d786 (post-V0.6). First run 2026-10-26, Windows 11, Python 3.11.9.
No js_api surface (no JS repo; js_api unchanged since the V0.3 holdout).
SECURITY LIMITATION: no Docker; LocalExecutor with scrubbed env (see docs/BENCHMARK_DESIGN.md).
