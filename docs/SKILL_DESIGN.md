# Regression Firewall — Agent Skill Design

Version: 0.1 (2026-10-04)

## 1. Division of responsibility

The project has two artifacts:

| Artifact | Contains | Must never contain |
|---|---|---|
| `regression-firewall` CLI | All logic: capture, normalize, diff, classify, score, report | Agent-specific instructions |
| `SKILL.md` | Workflow rules: when to invoke, how to interpret, when a task may not be called complete | Implementation logic, verdict computation |

The skill is the Agent Integration Layer. Any agent that can read a Markdown
instruction file and run a shell command can use the tool. Core rules are
platform-neutral on purpose.

## 2. The contract the skill teaches

1. **Before** modifying existing behavior, run `regression-firewall baseline`
   when practical (a repo without a baseline cannot be checked afterwards).
2. **Record intent**: write `.regression-firewall/intent.json` (or pass
   `--intent`) describing exactly the behavior changes the user asked for.
   Intent comes from the *user's request*, never from "what the code now
   does".
3. **After** implementing, run `regression-firewall check`.
4. `BLOCK` ⇒ the task is **not complete**. Fix or get user confirmation.
5. `REVIEW` ⇒ inspect every reported change before proceeding; do not wave
   it through.
6. Unclear behavior changes must not be silently reclassified as intended.

## 3. Anti-gaming rules (the important part)

An agent under pressure to finish can make the tool say PASS by destroying
the measurement. The skill forbids, explicitly:

- Deleting or editing `baseline.json` to make a check pass.
- Disabling surfaces, emptying probe lists, or raising thresholds solely to
  turn a failing check green.
- Adding sweeping `ignore` entries to hide a reported change.
- Re-running `baseline` *after* the code change and presenting the resulting
  clean check as evidence of correctness.

Allowed config changes are those tied to the user's requirements, made for a
stated reason, and disclosed in the final response (e.g. "this task adds a
new endpoint; a probe for it was added and a fresh baseline captured").

> Never update the baseline just to silence a regression.

## 4. Interpretation guide

| Verdict | Skill instruction |
|---|---|
| PASS | Task may be reported complete; mention the check ran clean. |
| REVIEW | List the uncertain changes to the user; wait for or apply human judgment; do not declare done. |
| BLOCK | Fix the reported regressions (or negotiate the scope with the user). Re-run `check` until PASS/REVIEW is resolved. Never declare done. |

The skill also explains exit codes (0/1/3/70) so agents can branch on them.

## 5. Installation model

`SKILL.md` ships at the repository root. Users (or their agents) copy it into
the agent's skill directory:

- Claude Code: `~/.claude/skills/regression-firewall/SKILL.md`
- Cursor / OpenCode / Gemini CLI / others: equivalent skill/rule locations,
  or simply reference the file in the agent's instruction file.

The README carries the canonical per-agent install commands. The skill must
keep working even when the agent has never seen the repo docs: it
self-contains the workflow and the CLI contract.

## 6. Intent contract

Agents write `.regression-firewall/intent.json` before running `check`. The
format is plain JSON so any agent can produce it, and the CLI validates it
strictly (unknown keys are errors) so mistakes fail loudly instead of
silently no-op'ing. Entries: `surface`, `target` (glob), `category`,
optional `path` (JSON path without the `$.` prefix), optional
`before`/`after` constraints, and a human-readable `note` that appears in
the report next to the matched change.
