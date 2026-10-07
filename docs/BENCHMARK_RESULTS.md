# Real-World Benchmark Results

*Generated 2026-10-07T10:07:41Z by regression-firewall 0.1.0. Numbers are computed from benchmarks/results/latest.json — see docs/BENCHMARK_DESIGN.md for methodology.*

- Isolation: `local-scrubbed-env` (**SECURITY LIMITATION**: no container isolation available on this machine — scrubbed-environment local execution only)
- Repositories: 1 (pinned commits)
- Manifest hash: `71cc688d93e8`

## Metrics

| Metric | Value |
|---|---|
| cases_total | 1 |
| cases_ran_to_verdict | 0 |
| repository_setup_failures | 1 |
| infrastructure_failures | 0 |
| mutation_failures | 0 |
| timeouts | 0 |
| planted_regression_cases | 0 |
| detected_regressions | 0 |
| missed_regressions | 0 |
| false_positives | 0 |
| noise_or_control_cases | 0 |
| noise_or_control_clean | 0 |
| detection_recall | None |
| false_positive_rate | None |
| severity_accuracy | None |
| verdict_accuracy | None |

## Case detail

| Repo | Case | Type | Class | Verdict (expected → detected) |
|---|---|---|---|---|
| urllib3 | urllib3_verify | verify | REPOSITORY_SETUP_FAILURE | — → — |

## Findings (REGRESSION_FIREWALL_FAILURE cases)

None in this run.

FRESH FINAL HOLDOUT — independent of all development and validation work.
Frozen implementation: 8428a5b13cdd9d54807ee17a23ddbaef61173454
Run ONCE. Original results are final regardless of pass/fail.
