# Regression Firewall — Eval System

Version: 0.1 (2026-10-04)

The eval suite is the project's quality gate. It plants known regressions
into tiny real projects, runs the full `baseline → mutate → check` pipeline
through the real CLI in a subprocess, and scores detection. It is fully
deterministic — no LLM is involved.

## 1. Methodology

Each case is a directory `evals/cases/<nn>_<slug>/` containing:

| File | Purpose |
|---|---|
| `before/` | The project at baseline time (source files + `.regression-firewall.yml`) |
| `case.yml` | Metadata, optional `intent` block, `mutations` (find/replace pairs), `expect` block |
| `intent.json` | *(optional)* written into the project when the case tests intent matching |

Runner steps per case (fresh temp dir each time):

1. Copy `before/` into `tmp/project`.
2. `python -m regression_firewall baseline` (subprocess, cwd = project).
3. Apply `mutations` (exact find/replace on named files; failure to find is a
   case-authoring error, loud).
4. Write `intent.json` if the case defines one.
5. `python -m regression_firewall check --json-summary` → parse `report.json`.
6. Assert every entry in `expect.changes` exists with the expected
   classification (and severity, when specified).
7. Assert **no other changes** exist beyond the expected list (strict mode;
   extras are false positives or missed noise — either way a failure).
8. Assert `expect.verdict` matches.

HTTP cases use a dependency-free `http.server` app so the suite runs
anywhere with no extra packages and no port conflicts (the server manager
assigns a free port via `{port}` in `base_url`).

## 2. Case list (V0.1 = 20 cases)

| # | Case | Planted change | Expected classification / severity | Verdict |
|---|---|---|---|---|
| 01 | `http_status_401_to_400` | POST /login status 401→400 | UNEXPECTED / HIGH | BLOCK |
| 02 | `http_json_field_removed` | `email` removed from response | UNEXPECTED / HIGH | BLOCK |
| 03 | `http_json_field_added` | `debug` field added | UNCERTAIN / LOW | PASS |
| 04 | `http_field_type_changed` | `age` int → string | UNEXPECTED / MEDIUM | REVIEW |
| 05 | `http_expected_field_rename` | `username`→`display_name` **with intent** | both EXPECTED | PASS |
| 06 | `http_timestamp_noise` | none (live timestamp in response) | — | PASS |
| 07 | `http_request_id_noise` | none (fresh X-Request-ID header) | — | PASS |
| 08 | `http_header_change` | Cache-Control header changes | UNCERTAIN / LOW | REVIEW |
| 09 | `http_content_type_change` | JSON → text/plain | UNEXPECTED / MEDIUM | REVIEW |
| 10 | `cli_exit_code_regression` | exit 0→1 + message change | UNEXPECTED / HIGH | BLOCK |
| 11 | `cli_stdout_change` | message text changes | UNCERTAIN / LOW | REVIEW |
| 12 | `cli_stderr_change` | new stderr text | UNCERTAIN / LOW | REVIEW |
| 13 | `cli_generated_file` | script starts creating a watched file | UNCERTAIN / MEDIUM | REVIEW |
| 14 | `cli_temp_file_noise` | none (temp file written outside watch list) | — | PASS |
| 15 | `api_symbol_removed` | public class removed | UNEXPECTED / CRITICAL | BLOCK |
| 16 | `api_symbol_added` | new function added | UNCERTAIN / INFO | PASS |
| 17 | `api_signature_changed` | required param added | UNEXPECTED / MEDIUM | REVIEW |
| 18 | `api_expected_change` | symbol removed **with intent** | EXPECTED | PASS |
| 19 | `multiple_regressions` | HTTP status flip + field removed + CLI exit flip | 3 × UNEXPECTED / HIGH | BLOCK |
| 20 | `no_regression` | none (deterministic output) | — | PASS |

## 3. Metrics

Aggregated over all cases by `evals/runner.py`:

- **Detection recall** — detected planted `UNEXPECTED` regression entries ÷
  total planted `UNEXPECTED` entries.
- **False-positive rate** — cases producing any extra (unplanned) change ÷
  total cases. Target: 0.
- **Severity accuracy** — planted entries whose detected severity matches ÷
  planted entries.
- **Expected-change accuracy** — intent-marked changes classified `EXPECTED`
  ÷ intent-marked changes (cases 05, 18).
- **Verdict accuracy** — cases whose verdict matches `expect.verdict` ÷ cases.

## 4. Running

```bash
python -m evals.runner                 # all cases, prints table + summary
python -m evals.runner --filter 0      # cases whose id starts with "0"
```

Results are written to `evals/results/` (git-ignored). The suite is also
wired into pytest (`tests/integration/test_evals.py`) and CI.

## 5. Current results

Run at V0.1 completion (2026-10-04, Windows 11, Python 3.11):

| Metric | Value |
|---|---|
| Cases passed | 20 / 20 |
| Detection recall | 100% |
| False-positive rate | 0% |
| Severity accuracy | 100% |
| Expected-change accuracy | 100% (cases 05, 18) |
| Verdict accuracy | 100% |

Reproduce with `python -m evals.runner` (also wired into pytest and CI).
Results land in `evals/results/summary.json`.
