# CI Integration (GitHub Action)

Regression Firewall ships a composite GitHub Action in this repository
(`action.yml`), so a pull request that changes behavior nobody asked for
fails CI — the same baseline → intent → check contract the agent follows,
applied to every PR.

```yaml
# .github/workflows/regression-firewall.yml
name: Regression Firewall
on:
  pull_request:

jobs:
  behavior:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v5
      - uses: Tong-bit-art/regression-firewall@v0.3.0
        with:
          base-ref: ${{ github.event.pull_request.base.sha }}
          project-path: .            # where .regression-firewall.yml lives
          # intent-file: intent.json # committed by your agent (optional)
          # fail-on: review          # default: only BLOCK fails the job
          # install-command: pip install -r requirements.txt
          # tool-install-command: pip install git+https://github.com/Tong-bit-art/regression-firewall@v0.3.0
```

## How it works

1. Checks out **base-ref** into `.regfw-base/` and the head ref into
   `.regfw-head/` (input `head-ref` overrides the triggering ref — used by
   this repository's own dogfood workflow).
2. Runs `regression-firewall baseline` in the base checkout (the project's
   committed `.regression-firewall.yml` defines the probes).
3. Copies the baseline into the head checkout and runs
   `regression-firewall check` against the PR's code.
4. Maps the verdict to the job:
   - **PASS** → success
   - **REVIEW** → warning annotation; fails the job only with
     `fail-on: review`
   - **BLOCK** → error annotation and job failure
   - tool error (exit 70/2) → error annotation and job failure
5. Writes the full Markdown report to the **job summary** and uploads
   `report.json` / `report.md` as the `regression-firewall-report` artifact
   (disable with `upload-artifacts: false`).

Outputs: `verdict` (PASS/REVIEW/BLOCK), `score` (0–100), `report-path`.

## Intent in CI

- **Agent-authored PRs**: commit `.regression-firewall/intent.json` (or any
  path) with the PR and point `intent-file` at it. The tool's post-hoc
  intent audit still applies: an intent file that appears only after
  behavior was already observed keeps the verdict at REVIEW.
- **Human PRs with no intent**: every detected behavior change is treated
  as unrequested — additive/uncertain ones (new optional fields, new
  symbols) produce REVIEW, breaking ones BLOCK. Teams that want change
  freedom set `fail-on: review` and treat the job as a report.

## Honesty notes

- The **config hash guard works in CI**: if the PR edits
  `.regression-firewall.yml` (probes, thresholds, ignores), the check
  carries a loud config-changed warning in the report — review such PRs
  with extra care.
- **Absolute paths in CLI output**: the two checkouts live in different
  directories. The tool rewrites the probe's working directory to `.` in
  captured stdout/stderr, so identical behavior diffs clean. Output that
  embeds *other* absolute paths that vary per checkout will still diff —
  prefer relative paths in CLI output, or mask with
  `normalization.custom_rules`.
- The baseline is captured fresh on every run from base-ref — there is no
  stored baseline to tamper with, and the re-baseline guard does not apply
  (each PR is its own comparison).
- `tool-install-command` overrides how the tool itself is installed; use it
  to pin a ref or install from a checkout. The default installs from PyPI
  (`version` input, default `>=0.3.0`).

## Dogfooding

This repository runs the action against its own `examples/cli` project on
every change that touches the action or the examples:
`.github/workflows/action-demo.yml`. Job 1 asserts the PASS path; job 2
asserts the BLOCK path against the `ci/action-demo-block` fixture branch
(one planted exit-code regression, kept minimal on purpose).
