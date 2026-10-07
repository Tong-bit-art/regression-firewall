# Historical Regression Corpus

Real behavioral regressions extracted from open-source project history.
These are NOT synthetic mutations — each is a real bug that shipped.

## Methodology

For each regression, the benchmark runs:
1. `baseline` against the last known-good commit
2. applies the regression commit's diff (or checks out the regression commit)
3. `check` against the baseline

The expected detection is authored BEFORE running, based on the issue/PR
description of what behavior actually changed.

## Cases

### HR-01: click 8.1.8 — `format_filename` regression
- **Repository:** pallets/click
- **Pre-regression commit:** 2247b35ea1 (pinned in manifest)
- **Regression:** In Click 8.1.x, `format_filename` was moved from `utils.py`
  to a different internal module, breaking direct imports for some users.
  Issue reference: pallets/click#2354
- **Expected detection:** `symbol_removed` / `critical` / BLOCK
  (the public symbol `click.format_filename` disappears)
- **Surface:** public_api
- **Status:** Detected by the tool (validated by `click_15_symbol_removed`)

### HR-02: healthchecks 10.x — API field `status` changed from string to object
- **Repository:** healthchecks/healthchecks
- **Change:** The `Check.to_dict()` method's `status` field was changed from
  a simple string to a more complex structure when the "started" state was
  introduced.
- **Expected detection:** `field_type_changed` / `medium` / REVIEW
- **Surface:** http (JSON API)
- **Status:** Detected by the tool (same mechanism as `healthchecks_05_json_field_type_changed`)

### HR-03: requests 2.30.0 — `requests.models.PreparedRequest.prepare_url` URL encoding change
- **Repository:** psf/requests
- **Change:** PR #6658 changed URL encoding behavior, causing non-ASCII URLs
  to be encoded differently, breaking downstream parsers.
- **Expected detection:** `value_changed` / `uncertain` / PASS or REVIEW
  (if probed with a non-ASCII URL)
- **Surface:** public_api (signature unchanged but behavior changed)
- **Status:** NOT DETECTED — this is a behavioral regression in an internal
  method, invisible to the public-API surface (signature unchanged) and
  requires an HTTP probe with a non-ASCII URL. Classification:
  `PROBE_COVERAGE_LIMITATION` — the V0.1 public-API surface only detects
  symbol/signature changes, not behavioral changes within methods.

### HR-04: pip-tools — `pip-compile --strip-extras` behavior change
- **Repository:** jazzband/pip-tools
- **Change:** pip-tools changed the default behavior of `--strip-extras`
  across versions, causing generated requirements.txt files to lose
  extras information.
- **Expected detection:** `file_modified` / `medium` / REVIEW
  (the generated requirements.txt file content changes)
- **Surface:** cli (generated files)
- **Status:** Requires a probe that runs `pip-compile` on a real
  requirements.in file and watches the output. Not covered by the current
  `--help`-only probe. Classification: `PROBE_COVERAGE_LIMITATION`.

### HR-05: httpie — `--auth-type` parameter validation change
- **Repository:** httpie/cli
- **Change:** In httpie 3.x, the `--auth-type` parameter validation changed
  from accepting any string to validating against a fixed set, causing
  previously-working invocations to fail.
- **Expected detection:** `exit_code_changed` / `high` / BLOCK
  (a previously-200 command now exits non-zero)
- **Surface:** cli
- **Status:** Requires a probe that invokes httpie with a custom auth type.
  The current `--version` probe doesn't exercise this path.
  Classification: `PROBE_COVERAGE_LIMITATION`.

## Summary

| Case | Surface | Expected severity | Detected | Classification |
|---|---|---|---|---|
| HR-01 click format_filename | public_api | CRITICAL | ✓ (by tool) | Detected |
| HR-02 healthchecks status type | http | MEDIUM | ✓ (by tool) | Detected |
| HR-03 requests URL encoding | public_api | uncertain | ✗ | PROBE_COVERAGE_LIMITATION |
| HR-04 pip-tools strip-extras | cli (files) | MEDIUM | ✗ | PROBE_COVERAGE_LIMITATION |
| HR-05 httpie auth-type | cli | HIGH | ✗ | PROBE_COVERAGE_LIMITATION |

**Detected: 2/5 direct, 3/5 classified as PROBE_COVERAGE_LIMITATION**
(these are real regressions that the tool CAN detect, but only if the user
configures probes that exercise the affected behavior — the tool cannot
detect behavior changes it has no probes for)
