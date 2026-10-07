# Real-World Benchmark Results

*Generated 2026-10-07T14:15:04Z by regression-firewall 0.1.0. Numbers are computed from benchmarks/results/latest.json — see docs/BENCHMARK_DESIGN.md for methodology.*

- Isolation: `local-scrubbed-env` (**SECURITY LIMITATION**: no container isolation available on this machine — scrubbed-environment local execution only)
- Repositories: 8 (pinned commits)
- Manifest hash: `e87c38e2a3e7`

## Metrics

| Metric | Value |
|---|---|
| cases_total | 66 |
| cases_ran_to_verdict | 66 |
| repository_setup_failures | 0 |
| infrastructure_failures | 0 |
| mutation_failures | 0 |
| timeouts | 0 |
| planted_regression_cases | 29 |
| detected_regressions | 29 |
| missed_regressions | 0 |
| false_positives | 0 |
| noise_or_control_cases | 37 |
| noise_or_control_clean | 37 |
| detection_recall | 1.0 |
| false_positive_rate | 0.0 |
| severity_accuracy | 1.0 |
| verdict_accuracy | 1.0 |

## Case detail

| Repo | Case | Type | Class | Verdict (expected → detected) |
|---|---|---|---|---|
| flaskr | flaskr_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| flaskr | flaskr_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| flaskr | flaskr_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| flaskr | flaskr_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| flaskr | flaskr_02_status_200_to_500 | status_200_to_500 | BENCHMARK_PASS | BLOCK → BLOCK |
| flaskr | flaskr_01_status_redirect_to_400 | status_redirect_to_400 | BENCHMARK_PASS | BLOCK → BLOCK |
| flaskr | flaskr_07_header_change | header_change | BENCHMARK_PASS | REVIEW → REVIEW |
| flaskr | flaskr_08_timestamp_noise | timestamp_noise | BENCHMARK_PASS | PASS → PASS |
| flaskr | flaskr_09_request_id_noise | request_id_noise | BENCHMARK_PASS | PASS → PASS |
| flaskr | flaskr_19_intent_expected_status | intent_expected_status | BENCHMARK_PASS | PASS → PASS |
| flaskr | flaskr_20_intent_mismatch_stays_unexpected | intent_mismatch_status | BENCHMARK_PASS | BLOCK → BLOCK |
| healthchecks | healthchecks_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| healthchecks | healthchecks_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| healthchecks | healthchecks_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| healthchecks | healthchecks_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| healthchecks | healthchecks_01_status_401_to_400 | status_401_to_400 | BENCHMARK_PASS | BLOCK → BLOCK |
| healthchecks | healthchecks_02_status_200_to_500 | status_200_to_500 | BENCHMARK_PASS | BLOCK → BLOCK |
| healthchecks | healthchecks_03_json_field_removed | json_field_removed | BENCHMARK_PASS | BLOCK → BLOCK |
| healthchecks | healthchecks_04_json_field_added | json_field_added | BENCHMARK_PASS | PASS → PASS |
| healthchecks | healthchecks_05_json_field_type_changed | json_field_type_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| healthchecks | healthchecks_07_header_change | header_change | BENCHMARK_PASS | REVIEW → REVIEW |
| healthchecks | healthchecks_08_timestamp_noise | timestamp_noise | BENCHMARK_PASS | PASS → PASS |
| healthchecks | healthchecks_09_request_id_noise | request_id_noise | BENCHMARK_PASS | PASS → PASS |
| healthchecks | healthchecks_19_intent_rename | intent_expected_rename | BENCHMARK_PASS | PASS → PASS |
| healthchecks | healthchecks_20_intent_mismatch_stays_unexpected | intent_mismatch_status | BENCHMARK_PASS | BLOCK → BLOCK |
| requests | requests_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| requests | requests_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| requests | requests_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| requests | requests_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| requests | requests_15_symbol_removed | symbol_removed | BENCHMARK_PASS | BLOCK → BLOCK |
| requests | requests_16_symbol_added | symbol_added | BENCHMARK_PASS | PASS → PASS |
| requests | requests_17_signature_changed | signature_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| click | click_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| click | click_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| click | click_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| click | click_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| click | click_15_symbol_removed | symbol_removed | BENCHMARK_PASS | BLOCK → BLOCK |
| click | click_16_symbol_added | symbol_added | BENCHMARK_PASS | PASS → PASS |
| click | click_17_signature_changed | signature_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| sherlock | sherlock_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| sherlock | sherlock_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| sherlock | sherlock_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| sherlock | sherlock_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| sherlock | sherlock_10_exit_0_to_1 | exit_0_to_1 | BENCHMARK_PASS | BLOCK → BLOCK |
| sherlock | sherlock_11_stdout_changed | stdout_changed | BENCHMARK_PASS | REVIEW → REVIEW |
| sherlock | sherlock_12_stderr_introduced | stderr_introduced | BENCHMARK_PASS | REVIEW → REVIEW |
| sherlock | sherlock_13_generated_file | generated_file_added | BENCHMARK_PASS | REVIEW → REVIEW |
| sherlock | sherlock_14_temp_file_noise | temp_file_noise | BENCHMARK_PASS | PASS → PASS |
| typer | typer_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| typer | typer_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| typer | typer_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| typer | typer_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| typer | typer_15_symbol_removed | symbol_removed | BENCHMARK_PASS | BLOCK → BLOCK |
| typer | typer_16_symbol_added | symbol_added | BENCHMARK_PASS | PASS → PASS |
| typer | typer_13_generated_file | generated_file_added | BENCHMARK_PASS | REVIEW → REVIEW |
| httpie | httpie_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| httpie | httpie_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| httpie | httpie_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| httpie | httpie_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| httpie | httpie_12_stderr_introduced | stderr_introduced | BENCHMARK_PASS | REVIEW → REVIEW |
| httpie | httpie_13_generated_file | generated_file_added | BENCHMARK_PASS | REVIEW → REVIEW |
| pip-tools | pip_tools_ctl_no_change#1 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| pip-tools | pip_tools_ctl_no_change#2 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| pip-tools | pip_tools_ctl_no_change#3 | no_change_control | BENCHMARK_PASS | PASS → PASS |
| pip-tools | pip_tools_ctl_non_behavior | non_behavior_change_control | BENCHMARK_PASS | PASS → PASS |
| pip-tools | pip_tools_11_stdout_changed | stdout_changed | BENCHMARK_PASS | REVIEW → REVIEW |

## Findings (REGRESSION_FIREWALL_FAILURE cases)

None in this run.

SECURITY LIMITATION: no Docker on this machine; LocalExecutor with a
scrubbed environment is used and recorded per-run. See BENCHMARK_DESIGN.md.
FastAPI-app exclusion: no small self-contained offline-runnable FastAPI
application met the selection criteria this round; the HTTP surface is
covered by two real WSGI apps (flaskr, healthchecks) instead.
healthchecks runs on Python 3.14 (Django 6.1 requires >= 3.12); the
venv_command override below is machine-specific and documented here.
