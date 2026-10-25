# Regression Firewall

> A behavioral regression safety layer for AI coding agents.

[![Tests](https://github.com/Tong-bit-art/regression-firewall/actions/workflows/test.yml/badge.svg)](https://github.com/Tong-bit-art/regression-firewall/actions/workflows/test.yml)
![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
![Platforms](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status: Beta](https://img.shields.io/badge/status-beta-orange)](CHANGELOG.md)

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

## What it checks

| Surface | Captures | Detects |
|---|---|---|
| **HTTP** | status, headers, cookies, JSON body (structured), content-type — GET/POST/PUT/PATCH/DELETE; probes can be derived from an OpenAPI 3.x document or generated from real routes via `discover --emit-probes` | status flips, removed/added/retyped fields, payload shape, header and cookie changes |
| **CLI** | stdout, stderr, exit code, watched files *and watched directories*; opt-in tracing of **filesystem writes**, **environment-variable reads** (names only) and **sqlite3 query shapes + write tables** (Python commands) | exit-code flips, output changes, new/deleted/modified files anywhere under a watched directory, new or vanished write targets, new or dropped env-var dependencies, query-set and query-count changes (N+1 signal), new or dropped write tables |
| **Public API (Python)** | importable symbols, signatures, `__all__`, submodules | removed symbols (CRITICAL), signature changes, export changes |
| **JS/TS API** | static extraction of ESM/CJS exports from entry files, incl. one-hop re-export resolution (`export {x} from`, `export * from`) — nothing is executed | removed exports (CRITICAL), new exports, signature/kind changes |
| **Volatile data** | — | masked by built-in normalizers plus *your own* custom rules (regex + key hints) |

Not (yet): database behavior, performance, browser UI, message queues. See
[Roadmap](#roadmap).

## Installation

Requires Python 3.9+.

> **Note:** Regression Firewall is **not yet on PyPI.** Automated publishing
> is prepared (tag-driven release workflow; PyPI via Trusted Publishers —
> see [docs/RELEASE.md](docs/RELEASE.md)). Until the first PyPI upload,
> install from a clone of this repository:

```bash
git clone https://github.com/Tong-bit-art/regression-firewall
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

# 2. Generate HTTP probes from your app's real routes (FastAPI/Flask/Starlette
#    apps are found by convention), then paste them into .regression-firewall.yml
regression-firewall discover --emit-probes

# 3. Declare anything else to watch: CLI commands, public API modules
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

## Use it in CI

The repository ships a composite GitHub Action — point it at a PR and an
unrequested behavior change fails the check, with the full report in the
job summary:

```yaml
- uses: Tong-bit-art/regression-firewall@v0.3.0
  with:
    base-ref: ${{ github.event.pull_request.base.sha }}
    project-path: .
    # intent-file: intent.json   # optional, committed by your agent
    # fail-on: review            # default: only BLOCK fails
    # install-command: pip install -r requirements.txt
```

See [docs/CI.md](docs/CI.md) for inputs, intent handling, and honesty
notes (this repository dogfoods the action on its own examples).

For the `public_api` surface, run the tool where your project's code is
importable: introspection uses the interpreter that runs
`regression-firewall`, so install it into the project's virtualenv (or run
it with that interpreter). Otherwise API probes may import a different copy
of the package — or fail.

## Commands

| Command | Purpose |
|---|---|
| `init` | Detect the project, scaffold `.regression-firewall.yml` |
| `discover` | Show detected language/framework and configured surfaces; lists FastAPI/Flask/Starlette app candidates found by convention |
| `discover --emit-probes [MODULE:ATTR]` | Generate ready-to-paste HTTP probes from an app's **real routes** (spec defaults to the best auto-detected app); parameterized paths are excluded with a note |
| `baseline` | Capture current behavior into `.regression-firewall/baseline.json` |
| `check` | Re-capture, diff against baseline, classify, score, write `report.json` + `report.md` |
| `check --select` | Capture only probes whose tracked paths intersect the changed-file set (opt-in; skips are recorded, unknown deps always run) |
| `report` | Re-display the latest report (`--format console\|markdown\|json`) |
| `explain <id>` | Full detail for one change |
| `import-openapi` | Preview the HTTP probes an OpenAPI 3.x document would generate |

## Configuration

Zero config works — defaults enable all surfaces; you add probes. Highlights:

```yaml
surfaces:
  http:
    ready_timeout: 30     # seconds to wait for the managed server; raise
                          # it if your server resolves DNS slowly on bind
    openapi:              # derive HTTP probes from an OpenAPI 3.x document
      file: openapi.yaml  # values for {path} params via `set:` — docs/OPENAPI_IMPORT.md
      set: {userId: "1"}

  cli:
    probes:
      - id: build
        command: ["python", "build.py"]
        files: ["out/receipt.json"]
        dirs:                       # watch whole directories, not just files
          - path: out/
            ignore: ["*.tmp", "__pycache__"]
            max_files: 2000
        trace:                      # opt-in behavior tracing (Python commands)
          fs_writes: true           # record which paths the command writes
          env_reads: true           # record which env var NAMES it reads
          sqlite: true              # record sqlite3 query shapes + write tables

  js_api:
    probes:
      - id: entry
        file: src/index.ts          # static export extraction (ESM/CJS/re-exports)

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
  custom_rules:           # your own masking for project-specific noise
    - name: order_ref
      pattern: '^[A-Z]{3}-[0-9]{6}$'
      key_hints: [ref, order]      # optional: fire only under matching keys
      placeholder: '<ORDER_REF>'

severity_overrides:       # "category" or "surface:category"
  header_changed: medium
```

After a `check`, reports also list **which files changed since the baseline**
(git diff + dirty working tree) as a correlation hint — it never affects the
verdict.

See [docs/NORMALIZATION.md](docs/NORMALIZATION.md) for the full rule catalog
and [docs/OPENAPI_IMPORT.md](docs/OPENAPI_IMPORT.md) for OpenAPI generation
rules.

## Evals & Evidence

Regression Firewall's detection is limited to behavior surfaces exercised
by configured probes. It cannot detect behavior that no probe covers.

### Bundled eval (synthetic)

23 hand-built cases: status flips, removed fields, type changes, exit-code
flips, symbol removals, noise, intent. Runs the actual CLI end-to-end.

**23/23 passed.** See [docs/EVALS.md](docs/EVALS.md).

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

### Fresh holdout (V0.3 code, 2026-10-25)

3 new repos never used in development: **zod** (real TypeScript barrel for
the `js_api` surface — `export *` chains, `.js`→`.ts` specifiers, generic
clauses), **isort** (CLI + the V0.3 `trace.fs_writes` path), **dateutil**
(public API, src layout). 21 cases: **recall 100%** (9/9 planted
regressions), **FPR 0%** (12/12 controls clean), severity and verdict
accuracy 100%. The one first-run failure was a benchmark authoring error
(isort's `main()` returns instead of raising SystemExit — verified
empirically), corrected and documented; parser gaps found while authoring
the zod corpus were fixed with tests before the manifest froze. See
[docs/FINAL_HOLDOUT_V03.md](docs/FINAL_HOLDOUT_V03.md). This corpus is now
consumed; the next release cycle needs a fresh one.

### Fresh holdout (V0.2 code, 2026-10-25)

3 new repos never used in development (tqdm, attrs, black — CLI, public-API
src-layout, and the V0.2 directory-watch path). 26 cases: **recall 100%**
(12/12 planted regressions), **FPR 0%** (14/14 controls clean), severity and
verdict accuracy 100%. The tool code was unchanged across all runs; every
intermediate failure was a benchmark-authoring or infrastructure issue
(formatter-cache-shielded probe, impossible expectation, state leak via
clean-excludes — all documented). See
[docs/FINAL_HOLDOUT_V02.md](docs/FINAL_HOLDOUT_V02.md). This corpus is now
consumed; the next release cycle needs a fresh one.

### Historical holdout (V0.1, consumed 2026-10-07)

3 repos (bottle, urllib3, packaging). Run once on 2026-10-07; the run
exposed benchmark and coverage issues that were fixed the same day.
Post-fix validation: 7/7 per repo — labeled POST-FIX, not a holdout result.
See [docs/FINAL_HOLDOUT.md](docs/FINAL_HOLDOUT.md) and
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

- **HTTP probes must be configured.** `discover --emit-probes` generates them
  from a FastAPI/Flask/Starlette app's real routes (apps are found by
  convention), and OpenAPI documents can derive a probe suite — but POST/PUT
  bodies are not invented, and parameterized paths need concrete values
  (list them yourself or use the OpenAPI import).
- **JS/TS API extraction is static and deliberately conservative.** It
  parses ESM exports, `export default`, alias lists, CommonJS
  `exports.NAME`, and re-exports (relative specifiers only, depth 3).
  Minified code, dynamic exports, destructured `export const {a} = ...`,
  bundler path aliases, object-literal `module.exports = {...}`, class
  members, and `export =` syntax are not understood — a construct the
  parser cannot see is invisible, not guessed at.
- **Behavior tracing is Python-only** (a `sitecustomize.py` is injected via
  PYTHONPATH). It records write *paths*, env-var *names*, and — with
  `trace.sqlite` — normalized query shapes/counts and write tables for
  **stdlib sqlite3 only** (other drivers, ORMs, and network databases are
  invisible). `os.fdopen`-style fd writes and non-Python child processes
  are invisible.
- **CLI watching is explicit.** Files and directories are watched because
  you listed them (`files` / `dirs`, with ignore globs and a per-dir
  `max_files` cap). Unknown files outside watched locations are not noticed.
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

- **V0.2** *(shipped 2026-10)* — OpenAPI import, custom normalization rules,
  CLI directory watching, git-diff hints in reports
- **V0.3** *(shipped 2026-10)* — convention-based HTTP discovery +
  `discover --emit-probes`; JS/TS public API surface (static, zero-dep);
  CLI behavior tracing (filesystem writes + env-var reads, Python only).
  Configuration-drift detection is covered by the existing `files:` watch
  plus trace read visibility; a dedicated mechanism was deliberately not
  built.
- **V0.4+** — database behavior (query counts, N+1 signals); selective
  regression analysis; opt-in performance regression. *(The V1.0
  "CI integration mode" item was pulled forward and shipped as the
  official GitHub Action — see [docs/CI.md](docs/CI.md).)*
- **V0.5** — selective regression analysis (run only affected surfaces)
- **V0.6** — opt-in performance regression

Full plan: [docs/ROADMAP.md](docs/ROADMAP.md). Architecture:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Every bug
fix that changes detection behavior must come with an eval case or test.

## License

[MIT](LICENSE)
