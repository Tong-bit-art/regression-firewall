# Regression Firewall — Product Requirements Document (PRD)

Version: 0.1 (2026-10-04)
Status: Active

## 1. Problem

AI coding agents are good at making the change you asked for and silent about
everything else they altered on the way. A task like *"add account lockout to
the login endpoint"* can also flip `401` to `400`, change an error schema,
break an exit code, or delete a public symbol. Unit tests written against the
new requirement will not catch any of that, because the old behavior was never
asserted anywhere.

> Your tests prove the new code works. Regression Firewall proves the old
> behavior still works.

Regression Firewall is a **behavioral regression safety layer for AI coding
agents**. It captures observable software behavior before an AI modification,
captures it again afterwards, and reports every behavior change that the user
did not ask for.

## 2. Users

1. **Developers using AI coding agents** (Claude Code, Codex, Cursor,
   OpenCode, Gemini CLI, ...) who want a safety net around agent edits.
2. **The agents themselves**, guided by the bundled Agent Skill
   (`SKILL.md`), which tells them when and how to run the tool and forbids
   declaring a task complete while the verdict is `BLOCK`.
3. **Reviewers / CI**, which consume the Markdown and JSON reports.

## 3. Core workflow

```
regression-firewall baseline     # capture behavior before the change
  ... agent modifies code, writes intent ...
regression-firewall check        # re-capture, diff, classify, score, verdict
```

The agent (or user) records *intent* — what behavior changes were requested —
in a structured `intent.json`. The tool deterministically classifies every
detected change as `EXPECTED`, `UNEXPECTED`, or `UNCERTAIN` and produces a
verdict:

- **PASS** — no significant unintended behavior change.
- **REVIEW** — medium-risk or uncertain changes need a human look.
- **BLOCK** — high/critical unintended regression; the agent must not declare
  the task complete.

## 4. V0.1 scope

### Behavior surfaces

| Surface | What it captures | Detection highlights |
|---|---|---|
| **HTTP** | status, headers, cookies, JSON body structure and values, content-type | `status_changed`, `field_removed`, `field_added`, `field_type_changed`, `header_changed`, `cookie_changed`, `content_type_changed`, `response_shape_changed` |
| **CLI** | stdout, stderr, exit code, generated files (explicit watch list) | `exit_code_changed`, `stdout_changed`, `stderr_changed`, `file_created`, `file_deleted`, `file_modified` |
| **Public API (Python)** | importable public symbols, kinds, signatures, `__all__`, submodules | `symbol_removed`, `symbol_added`, `signature_changed`, `export_changed` |

HTTP probes support GET, POST, PUT, PATCH, DELETE and full request/response
recording. JSON responses are compared structurally, not textually.

### Explicitly out of scope for V0.1

Database query regressions, N+1 detection, performance benchmarking, browser
UI/visual regression, message queues, distributed tracing, production
telemetry, full LSP dependency graphs, cross-repository analysis. See
`ROADMAP.md`. No speculative abstraction may be added "for" these.

### Non-goals (permanent)

- Regression Firewall does not write business code.
- It is not a linter, code reviewer, style checker, or unit-test generator.
- It is not a snapshot-testing library: it compares *behavior across a code
  change*, not a captured output against a golden file committed to the repo.

## 5. Product principles

1. **Verification first.** LLM reasoning may classify and explain, but every
   detection, diff, score, and verdict must be producible by deterministic
   code. *Never use an LLM where deterministic comparison is sufficient.*
2. **Low false positives.** Timestamps, UUIDs, request IDs, tokens, temp
   paths, float noise, durations, and volatile headers must be normalized
   before diffing. A run that floods the user with meaningless diffs is a
   failed run.
3. **Intent-aware.** `changed ≠ regression`. Changes the user asked for are
   `EXPECTED`. Expected comes from *user intent*, never from "the code
   changed, so it was intended".
4. **Explainable.** Every finding answers: what changed, before, after, why
   it matters, was it requested, how confident are we, what to verify.
5. **Agent neutral.** All logic lives in a standalone CLI. The skill is a
   thin integration layer; no agent platform is privileged.

## 6. Success criteria for V0.1

A developer can really run:

```
regression-firewall baseline
# AI modifies the code
regression-firewall check
```

and the tool accurately tells them *what else changed besides what they asked
for*, with low noise. Measured by the eval suite (`EVALS.md`):

- Regression detection recall ≥ 95% on planted regressions.
- False-positive rate ≈ 0 on noise-only and no-change cases.
- Verdict accuracy 100% across the 20 eval cases.
- Runtime overhead small enough to run per task (seconds, not minutes).

## 7. Commands (V0.1)

| Command | Purpose |
|---|---|
| `init` | Detect project, scaffold `.regression-firewall.yml`, create artifacts dir |
| `discover` | Report project type, frameworks, configured/detected behavior surfaces |
| `baseline` | Capture current behavior → `.regression-firewall/baseline.json` |
| `check` | Re-capture, diff against baseline, classify, score → `latest.json`, `report.json`, `report.md` |
| `report` | Re-display the latest report (console / markdown / json) |
| `explain` | Print full detail for one change id from the latest report |

Exit codes for `check`: `0` = PASS, `1` = REVIEW, `3` = BLOCK, `70` = runtime
error. Other commands: `0` on success, `70` on runtime error.

## 8. Configuration

Single YAML file `.regression-firewall.yml` (JSON also accepted). Zero
configuration is valid: defaults enable all three surfaces with the probe
lists the user defines. Normalization rules are individually switchable, and
severity per category can be overridden. See `docs/NORMALIZATION.md` and
`docs/RISK_MODEL.md`.

## 9. Anti-gaming requirements

The tool assumes an automated reader that may be motivated to make the check
go away. Therefore:

- The baseline is never rewritten by `check`; weakening config between
  baseline and check produces a visible warning.
- The skill instructions forbid deleting baselines, disabling surfaces, or
  raising thresholds to make a failing implementation pass.
- Verdicts are computed deterministically and reproducibly.

## 10. Risks

| Risk | Mitigation |
|---|---|
| False positives destroy trust | Normalization engine + eval suite with noise cases; FPR is the primary metric |
| Agent games the tool | Skill hard rules + config-change warnings; documented in SKILL.md |
| HTTP probing needs a running server | Built-in optional server lifecycle management (`server.command`) |
| Importing user code is unsafe | Public API extraction runs in a short-lived subprocess with a timeout |
| Cross-platform drift | Pathlib everywhere, no shell assumption, CI on Windows/Linux/macOS |
