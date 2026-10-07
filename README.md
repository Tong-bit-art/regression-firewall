# Regression Firewall

> A behavioral regression safety layer for AI coding agents.

**AI changed the feature you asked for. What else did it change?**

Regression Firewall captures your software's observable behavior *before* an
AI agent edits the code, captures it again *after*, and reports every behavior
change the user did not ask for — with a deterministic, explainable verdict:

```
POST /login   before → 401 Unauthorized
              after  → 400 Bad Request

Regression Firewall:
  HIGH   POST /login  status_changed   401 → 400
  Existing clients may depend on HTTP 401.

Risk Score: 70 / 100
Verdict: BLOCK
```

Your tests prove the new code works. Regression Firewall proves the old
behavior still works.

---

## The problem it solves

Ask an agent to *"add account lockout to the login endpoint"* and it will —
tests and all. On the way it may also flip `401` to `400`, reshape the error
JSON, change a CLI exit code, or delete a public symbol. Nothing fails: your
new tests assert the *new* requirement, and the old behavior was never
asserted anywhere.

Regression Firewall closes that gap:

1. `regression-firewall baseline` — records what the code **currently does**.
2. The agent (or you) edits the code and records *intent*: the changes the
   user actually requested.
3. `regression-firewall check` — re-captures, structurally diffs, classifies
   every change as **EXPECTED / UNEXPECTED / UNCERTAIN**, scores risk, and
   returns **PASS / REVIEW / BLOCK**.

A `BLOCK` means: *something the user did not ask for broke.* The agent must
not call the task complete.

## What it checks (V0.1)

| Surface | Captures | Detects |
|---|---|---|
| **HTTP** | status, headers, cookies, JSON body (structured), content-type — GET/POST/PUT/PATCH/DELETE | status flips, removed/added/retyped fields, payload shape, header and cookie changes |
| **CLI** | stdout, stderr, exit code, watched generated files | exit-code flips, output changes, new/deleted/modified files |
| **Public API (Python)** | importable symbols, signatures, `__all__`, submodules | removed symbols (CRITICAL), signature changes, export changes |

Not (yet): JavaScript/TypeScript exports, database behavior, performance,
browser UI, message queues. See [Roadmap](#roadmap).

## Installation

Requires Python 3.9+.

> **Note:** Regression Firewall is **not yet published on PyPI.** Install
> from a clone of this repository:

```bash
git clone <repository-url>
cd regression-firewall
pip install .
```

The only runtime dependency is PyYAML. HTTP probing, subprocess capture, and
Python introspection all use the standard library.

## Quick start

```bash
cd your-project

# 1. Scaffold a config and detect what behavior exists
regression-firewall init

# 2. Declare what to watch: HTTP probes, CLI commands, public API modules
#    (.regression-firewall.yml)
```

```yaml
version: 1
surfaces:
  http:
    enabled: true
    server:                       # optional: the tool manages the server
      command: ["python", "app.py"]
    base_url: "http://127.0.0.1:{port}"   # {port} → a free port, passed via $REGFW_SERVER_PORT
    probes:
      - id: "POST /login"
        method: POST
        path: /login
        body: {"username": "alice", "password": "wrong"}
  cli:
    enabled: true
    probes:
      - id: deploy
        command: ["python", "deploy.py"]
        files: ["out/receipt.json"]     # generated files to watch
  public_api:
    enabled: true
    probes:
      - id: mypackage
        module: mypackage
```

```bash
# 3. Capture the current behavior
regression-firewall baseline

# ... the AI (or you) modifies the code ...

# 4. Re-capture, diff, and get a verdict
regression-firewall check
```

Working end-to-end examples live in [`examples/`](examples/) (FastAPI,
Flask, a CLI tool, and a Python library).

## How it works

```
baseline  ──►  capture (raw)  ──►  normalize (both sides)  ──►  structural diff
                                                                      │
              PASS ◄── risk score + verdict rules ◄── classification ◄┘
                                        ▲
                                intent (what was requested)
```

- **Normalize, don't flatter.** Timestamps, UUIDs, request IDs, tokens, temp
  paths, durations, float jitter, ANSI codes, and volatile headers are
  masked before diffing, so identical code produces a clean PASS
  ([docs/NORMALIZATION.md](docs/NORMALIZATION.md)).
- **Structure, not text.** JSON responses are compared recursively — a
  removed field is `field_removed` with its JSON path, not a line of noise.
- **Intent-aware.** Changes matching `intent.json` are EXPECTED and excluded
  from risk. Unexplained structural changes are UNEXPECTED; additive or
  content-level ones are UNCERTAIN and reported for human review.
- **Explainable scoring.** Each change contributes
  `severity points × confidence` to a 0–100 score; fixed verdict rules turn
  the score and the worst unexpected change into PASS / REVIEW / BLOCK
  ([docs/RISK_MODEL.md](docs/RISK_MODEL.md)).
- **Deterministic.** No LLM is involved anywhere in the pipeline. The same
  inputs always produce the same verdict.
- **No silent passes.** A probe that could not be captured on either side,
  or an intent entry that appeared after a check already observed the
  behavior (post-hoc intent), keeps the verdict at REVIEW and is called out
  in the report — re-running does not clear it.
- **Secrets stay out of snapshots.** Auth headers, cookie values, and
  secret-named body fields are masked at capture time, so the stored
  baseline/latest files are safe to share in bug reports.

## Agent integration

Copy [`SKILL.md`](SKILL.md) into your agent's skill directory:

```bash
# Claude Code
mkdir -p ~/.claude/skills/regression-firewall
cp SKILL.md ~/.claude/skills/regression-firewall/SKILL.md
```

For Cursor, OpenCode, Gemini CLI and other agents, reference the file from
the agent's rules/instructions. The skill teaches the agent the workflow
(baseline → intent → check) and the safety rules:

- never declare a task complete while the verdict is `BLOCK`;
- never update the baseline to silence a regression;
- never weaken the configuration solely to make a failing check pass;
- never reclassify an already-observed change with a late intent edit —
  post-hoc intent entries keep the verdict at REVIEW until the user
  explicitly acknowledges them (`check --accept-post-hoc-intent`).

`check` exit codes for scripting: `0` PASS · `1` REVIEW · `3` BLOCK · `2` usage error · `70` runtime error.

For the `public_api` surface, run the tool where your project's code is
importable: introspection uses the interpreter that runs
`regression-firewall`, so install it into the project's virtualenv (or run
it with that interpreter). Otherwise API probes may import a different copy
of the package — or fail.

## Commands

| Command | Purpose |
|---|---|
| `init` | Detect the project, scaffold `.regression-firewall.yml` |
| `discover` | Show detected language/framework and configured surfaces |
| `baseline` | Capture current behavior into `.regression-firewall/baseline.json` |
| `check` | Re-capture, diff against baseline, classify, score, write `report.json` + `report.md` |
| `report` | Re-display the latest report (`--format console\|markdown\|json`) |
| `explain <id>` | Full detail for one change |

## Configuration

Zero config works — defaults enable all surfaces; you add probes. Highlights:

```yaml
surfaces:
  http:
    ready_timeout: 30     # seconds to wait for the managed server; raise
                          # it if your server resolves DNS slowly on bind

thresholds:
  review_score: 30        # REVIEW at or above this score
  block_score: 70         # BLOCK at or above this score
  block_on_high: true     # HIGH unexpected changes block outright

ignore:
  headers: [date, content-length]
  json_paths: ["*.debug_trace"]

normalization:            # every rule individually switchable
  uuid: true
  epoch_timestamps: true
  tokens: true
  # ... see docs/NORMALIZATION.md

severity_overrides:       # "category" or "surface:category"
  header_changed: medium
```

See [docs/NORMALIZATION.md](docs/NORMALIZATION.md) for the full rule catalog.

## Evals & Evidence

Regression Firewall's detection is limited to behavior surfaces exercised
by configured probes. It cannot detect behavior that no probe covers.

### Bundled eval (synthetic)

20 hand-built cases: status flips, removed fields, type changes, exit-code
flips, symbol removals, noise, intent. Runs the actual CLI end-to-end.

**20/20 passed.** See [docs/EVALS.md](docs/EVALS.md).

### Validation corpus (real projects)

8 pinned open-source repos (Flask, Django, Click, argparse, Typer, pip-tools).
66 cases with planted regressions and controls.

| Metric | Value |
|---|---|
| Detection recall | **100%** |
| False positive rate | **0%** |
| Severity accuracy | **100%** |
| Verdict accuracy | **100%** |

### Historical regressions (real bugs)

5 real regressions from open-source history. 2 detected; 3 require probe
coverage the user must configure. See [docs/HISTORICAL_REGRESSIONS.md](docs/HISTORICAL_REGRESSIONS.md).

### Fresh holdout (never used for development)

3 new repos (bottle, urllib3, packaging). Run once on 2026-10-07; the run
exposed benchmark and coverage issues that were fixed the same day.
**Post-fix validation: 7/7 per repo** (3/3 planted regressions detected,
0 false positives) — not a holdout result. See
[docs/FINAL_HOLDOUT.md](docs/FINAL_HOLDOUT.md) and
[docs/FINAL_EVIDENCE_REPORT.md](docs/FINAL_EVIDENCE_REPORT.md).

### Independent agent validation (executed 2026-10-07)

A fresh-context agent (DeepSeek V4 Pro in OpenCode) executed the 10-task
protocol on two real repositories (Flask tutorial app, Sherlock CLI) with
only the workspace, natural-language tasks, and `SKILL.md`. Result:
**10/10 tasks, zero hard-rule violations**, and all three check-silencing
pressures (no-intent BLOCK, re-baseline demand, proceed-on-REVIEW) resolved
correctly. Findings and caveats:
[docs/INDEPENDENT_AGENT_VALIDATION.md](docs/INDEPENDENT_AGENT_VALIDATION.md).

### What Regression Firewall does not prove

- It cannot detect behavior that no configured probe exercises.
- It is not a replacement for unit/integration testing.
- It is not production observability.
- It does not prove semantic equivalence of arbitrary programs.

## Limitations (honest list)

- **HTTP probes must be configured.** `discover` can list routes for
  FastAPI/Flask apps via `discover.app`, but V0.1 does not auto-derive a
  full probe suite — you tell it what to watch.
- **Public API surface is Python only.** JS/TS exports are planned for V0.2.
- **CLI generated-file tracking uses an explicit watch list.** Unknown new
  files elsewhere are not noticed.
- **CLI free-text secrets.** Response headers/cookies/JSON bodies are
  redacted at capture time, but arbitrary secrets printed to stdout/stderr
  cannot be reliably identified and are stored raw (documented; no risky
  free-text regex scrubbing is attempted).
- **Behavior, not code.** If a behavior is never exercised by a probe, its
  regression is invisible.
- **Re-baselining is trusted.** Running `baseline` after editing code
  produces a clean check by definition; the tool cannot distinguish that
  from a legitimate re-baseline. Agents are bound by SKILL.md never to do
  this, and config changes between baseline and check produce a loud
  warning — review both when auditing an agent's work.
- **Cookie values are redacted in snapshots by default** (along with auth
  headers and secret-named body fields), so value-only cookie changes are
  not detected unless you set `redaction.secrets: false`.
- **Probes run your code.** Public-API introspection imports your package in
  a short-lived subprocess; HTTP servers are started as configured. Don't
  point it at production.
- **Platform status:**
  - Ubuntu, Windows, macOS — **tested via GitHub Actions**
    (Windows/macOS on Python 3.12/3.13, Ubuntu on 3.11/3.12/3.13 —
    all green).
  - Python 3.14 additionally passes the full suite locally.

## Roadmap

- **V0.2** — JS/TS public API, OpenAPI import, better HTTP discovery, git-diff hints
- **V0.3** — filesystem & environment behavior
- **V0.4** — database behavior (query counts, N+1 signals)
- **V0.5** — selective regression analysis (run only affected surfaces)
- **V0.6** — opt-in performance regression

Full plan: [docs/ROADMAP.md](docs/ROADMAP.md). Architecture:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Every bug
fix that changes detection behavior must come with an eval case or test.

## License

[MIT](LICENSE)
