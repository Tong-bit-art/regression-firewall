# Real-World Benchmark Results

*Generated 2026-10-25T12:20:00Z by regression-firewall 0.2.0. Numbers are computed from benchmarks/results/latest.json — see docs/BENCHMARK_DESIGN.md for methodology.*

- Isolation: `local-scrubbed-env` (**SECURITY LIMITATION**: no container isolation available on this machine — scrubbed-environment local execution only)
- Repositories: 3 (pinned commits)
- Manifest hash: `45803ef80ccc`

## Metrics

| Metric | Value |
|---|---|
| cases_total | 26 |
| cases_ran_to_verdict | 26 |
| repository_setup_failures | 0 |
| infrastructure_failures | 0 |
| mutation_failures | 0 |
| timeouts | 0 |
| planted_regression_cases | 12 |
| detected_regressions | 12 |
| missed_regressions | 0 |
| false_positives | 0 |
| noise_or_control_cases | 14 |
| noise_or_control_clean | 14 |
| detection_recall | 1.0 |
| false_positive_rate | 0.0 |
| severity_accuracy | 1.0 |
| verdict_accuracy | 1.0 |

## Case detail

| Repo | Case | Type | Class | Verdict (expected → detected) |
|---|---|---|---|---|
| tqdm | tqdm_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| tqdm | tqdm_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| tqdm | tqdm_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| tqdm | tqdm_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| tqdm | tqdm_10_exit_0_to_1 | exit_0_to_1 | BENCHMARK_PASS | BLOCK → BLOCK |
| tqdm | tqdm_11_stdout_changed | stdout_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| tqdm | tqdm_12_stderr_introduced | stderr_introduced | BENCHMARK_PASS | REVIEW → REVIEW |
| tqdm | tqdm_15_symbol_removed | symbol_removed | BENCHMARK_PASS | BLOCK → BLOCK |
| tqdm | tqdm_17_signature_changed | signature_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| tqdm | tqdm_16_symbol_added | symbol_added | BENCHMARK_PASS | PASS → PASS |
| attrs | attrs_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| attrs | attrs_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| attrs | attrs_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| attrs | attrs_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| attrs | attrs_15_symbol_removed | symbol_removed | BENCHMARK_PASS | BLOCK → BLOCK |
| attrs | attrs_17_signature_changed | signature_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| attrs | attrs_16_symbol_added | symbol_added | BENCHMARK_PASS | PASS → PASS |
| attrs | attrs_18_implementation_only | implementation_only | BENCHMARK_PASS | PASS → PASS |
| black | black_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| black | black_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| black | black_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| black | black_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| black | black_10_exit_0_to_1 | exit_0_to_1 | BENCHMARK_PASS | BLOCK → BLOCK |
| black | black_11_stdout_changed | stdout_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| black | black_13b_generated_file_dir_watch | generated_file_added | BENCHMARK_PASS | REVIEW → REVIEW |
| black | black_14_stray_file_noise | temp_file_noise | BENCHMARK_PASS | PASS → PASS |

## Findings (REGRESSION_FIREWALL_FAILURE cases)

None in this run.

FRESH HOLDOUT V0.2 — repos disjoint from all prior development/validation.
Frozen tool: 0.2.0 @ 09dbe56. First run 2026-10-25, Windows 11, Python 3.11.9.
No HTTP surface: V0.2 left HTTP capture/diff untouched (see header).
SECURITY LIMITATION: no Docker; LocalExecutor with scrubbed env (see docs/BENCHMARK_DESIGN.md).
