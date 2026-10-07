---
name: regression-firewall
description: Behavioral regression safety layer for AI coding agents. Capture a behavior baseline before modifying existing code, write the requested behavior changes as intent, run regression-firewall check after implementing, and treat BLOCK as "task not complete". Use when editing existing HTTP APIs, CLIs, or Python packages with an agent.
---

# Regression Firewall

A behavioral regression safety layer. Your tests prove the new code works;
Regression Firewall proves the old behavior still works.

You (the agent) must use this skill whenever you modify existing software
behavior. It does not write code and does not replace tests.

## When to run it

Run the workflow below whenever **all** of these hold:

1. The task modifies existing behavior (HTTP endpoints, CLI commands, or a
   Python package's public API) — not a greenfield project.
2. A baseline can be captured before you edit (the code currently runs).
3. The project has `.regression-firewall.yml` with probes — if not, and the
   user agrees, run `regression-firewall init` and add probes first.

Do not run it for pure refactors with no observable behavior, docs-only
changes, or new files with no existing consumers.

## The workflow

### Step 1 — Baseline (before editing code)

```bash
regression-firewall baseline
```

Never skip this step and never re-baseline after your edits "to get a clean
check". The baseline must reflect the behavior the user already has.

### Step 2 — Record intent (what the USER asked for)

Write `.regression-firewall/intent.json` describing exactly the behavior
changes the user requested — before you run check:

```json
{
  "schema_version": 1,
  "task": "Add account lockout after 5 failed logins.",
  "expected_changes": [
    {
      "surface": "http",
      "target": "POST /login",
      "category": "status_changed",
      "before": 401,
      "after": 423,
      "note": "locked accounts get 423"
    }
  ]
}
```

Fields per entry: `surface` (`http` | `cli` | `public_api` or `*`),
`target` (glob allowed — HTTP/CLI probe ids, or the dotted symbol path
`module.symbol` for `public_api` changes, e.g. `requests.api.get`),
`category` (e.g. `status_changed`, `field_added`, `field_removed`,
`exit_code_changed`, `symbol_removed`, `signature_changed`, or `*`),
optional `path` (JSON path without the `$.` prefix, glob allowed; unused for
`public_api` changes), optional `before`/`after` value constraints, and a
short `note`.

Rules for intent:

- Intent comes from the **user's request**, never from what your code now
  does. If you did not plan the change, do not list it.
- If a change is a plausible side effect you intend (e.g. a response field
  your feature adds), list it — that is what `field_added` entries are for.
- Never write an intent file that blanket-matches everything (`"*"` on all
  fields) to force a PASS. That is lying, and the report shows the notes.
- **Late intent edits are audited.** The tool records the intent state at
  baseline time and at every check. An entry that first appears (or is
  modified) after a previous check already observed the behavior is a
  POST-HOC INTENT CHANGE: it is marked in the report, the verdict stays at
  REVIEW, and re-running `check` does not clear it. To accept one, get the
  user's explicit approval and re-run `check --accept-post-hoc-intent` (the
  acknowledgement is recorded). Otherwise fix the change.

### Step 3 — Check (after editing, before claiming success)

```bash
regression-firewall check
```

Exit codes: `0` PASS, `1` REVIEW, `3` BLOCK, `70` tool error.

### Step 4 — Interpret

| Verdict | What it means | What you must do |
|---|---|---|
| **PASS** | No unintended behavior change detected. | You may report the task complete. Mention that the check ran clean. |
| **REVIEW** | Medium-risk or uncertain changes were found. | Read the report, explain each change to the user, and either fix it or get explicit user confirmation. **Do not** declare the task complete on your own. |
| **BLOCK** | A HIGH or CRITICAL unintended regression exists. | The task is **not complete**. Fix the regression (or negotiate the scope with the user), then re-run `check`. |

Read `report.md` / `report.json` for details. For any change, use
`regression-firewall explain <change_id>` to see full before/after detail.

## Hard rules

1. **Never declare a task complete while the verdict is BLOCK.**
2. **Never update or delete the baseline to make a check pass.** The baseline
   is the user's existing behavior, not an obstacle. Re-baselining after your
   edits only hides regressions. The tool enforces this: if the previous
   check reported BLOCK/REVIEW, `baseline` refuses without `--force`, and any
   forced re-baseline makes every later `check` print a
   **BASELINE TRUST WARNING**. If you ever need `--force`, stop and get
   explicit user approval first — a forced re-baseline in your final report
   without the user's request is a violation, not a workaround.
3. **Never weaken the configuration to silence a failing check** — do not
   disable surfaces, empty probe lists, raise thresholds, or add sweeping
   `ignore` entries just to turn BLOCK into PASS. Configuration may change
   only when the user's task genuinely requires it (e.g. the task adds a new
   endpoint that needs a probe), with the reason stated in your final report.
4. **Never classify an unexplained change as intended.** If you cannot
   explain a change, report it to the user as a finding.
5. **Do not edit `.regression-firewall/report.*` or snapshot files by hand**
   — snapshots carry an integrity hash and tampering is flagged.
6. **Never reclassify an already-observed change with a late intent edit.**
   If a check flagged a change and you only then decide it was intended,
   that is a POST-HOC INTENT CHANGE. The report will mark it and the verdict
   stays REVIEW; `check` re-runs do not clear it. Get explicit user approval
   and re-run `check --accept-post-hoc-intent` to record the acknowledgement
   — or fix the change. A probe that could not be captured is also never a
   PASS: the report says it was NOT verified.

## Configuration changes that ARE legitimate

- Adding probes for a new endpoint/command the user asked to build (then a
  fresh baseline is expected — say so).
- Extending `ignore.json_paths` for genuinely per-run-volatile data the
  default normalizer misses, with an example of the noise.
- Severity overrides the user explicitly requests.

Any config change must be disclosed in your final response.

## Quick reference

```bash
regression-firewall init       # scaffold config (new projects)
regression-firewall discover   # show detected surfaces and probes
regression-firewall baseline   # capture before-behavior
regression-firewall check      # capture after-behavior, diff, verdict
regression-firewall report     # re-display the last report
regression-firewall explain ID # detail for one change
```
