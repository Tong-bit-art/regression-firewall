# Regression Firewall — Architecture

Version: 0.1 (2026-10-04)

## 1. Pipeline

```
User / Coding Agent
        │
Regression Firewall Skill (SKILL.md)          ← integration layer only
        │
regression-firewall CLI                        ← all logic lives here
        │
┌──────────────────────────────────────────────┐
│ Project Discovery      (discovery/)          │
│ Intent Loading         (intent/)             │
│ Behavior Capture       (capture/)            │  ← baseline, then again after edits
│ Normalization          (normalize/)          │
│ Behavior Diff          (diff/)               │
│ Classification         (intent/matcher.py)   │
│ Risk Scoring           (scoring/)            │
│ Verdict + Reports      (report/)             │
└──────────────────────────────────────────────┘
        │
   PASS / REVIEW / BLOCK
```

Every stage is an independent module with a typed interface; the CLI wires
them together. No stage reads or writes another stage's files directly.

## 2. Module map

| Module | Responsibility | Key types |
|---|---|---|
| `models/` | Serializable data model for snapshots, changes, results | `Snapshot`, `ProbeCapture`, `Change`, `CheckResult` |
| `config/` | Defaults, `.regression-firewall.yml` loading, validation | `Config` (+ per-surface dataclasses) |
| `discovery/` | Language/framework detection, optional route discovery | `ProjectInfo` |
| `capture/` | Run probes, produce raw `ProbeCapture`s; HTTP server lifecycle | `run_capture()` |
| `normalize/` | Rule engine that masks volatile data before diffing | `Normalizer` |
| `diff/` | Structural comparison of normalized captures → `Change` list | surface `diff_*` functions |
| `intent/` | Intent file model + deterministic expectation matcher | `Intent`, `classify_change()` |
| `scoring/` | Severity tables, risk score, verdict | `score_changes()` |
| `report/` | Console, Markdown, JSON renderers | `render_console()` etc. |
| `cli.py` | argparse wiring, command implementations, exit codes | `main()` |

## 3. Key decisions

### D1 — Python core CLI

*Context.* The tool must run on Windows/macOS/Linux, be installable with pip,
and be trivially scriptable by agents.

*Decision.* Python ≥ 3.9 with a console script `regression-firewall`.
*Alternatives:* TypeScript (good, but heavier packaging story for a CLI that
must also introspect Python code), Rust (fast, but slow iteration and worse
introspection for a Python-first V0.1).
*Trade-offs:* interpreter startup time (~50 ms) is acceptable; GIL irrelevant
(workload is subprocess + I/O bound).

### D2 — One runtime dependency: PyYAML

`urllib` (HTTP probes), `subprocess` (CLI probes, API runner), `inspect`
(signatures), `hashlib`, `argparse`, `json`, `pathlib` are all stdlib.
Config is user-facing, so YAML (with comments) beats JSON/TOML for UX;
`tomllib` would cap the floor at Python 3.11. PyYAML is pure-Python
installable, ubiquitous, and stable.

### D3 — Raw capture, normalize at diff time

Snapshots store **raw** captured data. The normalizer is built from the
*current* config and applied to both sides inside the diff engine.
Consequences: changing normalization config does not invalidate baselines;
reports can show raw values when useful; snapshots stay an honest record.
`baseline.json` also stores a `config_hash` so `check` can warn when the
configuration (thresholds, ignores, surfaces) changed under a baseline.

### D4 — Subprocess isolation for code-touching capture

Public API extraction imports the user's package. That must never run inside
the CLI process (it can crash, hang, or mutate global state). It runs in a
short-lived `sys.executable` subprocess executing a bundled runner script,
with a hard timeout and JSON output. CLI probes are already subprocesses by
definition. HTTP servers are optionally managed subprocesses.

### D5 — Deterministic classification and scoring

Classification (`EXPECTED`/`UNEXPECTED`/`UNCERTAIN`) is a pure function of
(change, intent). Severity comes from a static per-category table with config
overrides. The risk score is an additive, explainable formula (see
`RISK_MODEL.md`). No LLM is required anywhere in the V0.1 pipeline; agents
supply *intent*, not verdicts.

## 4. Snapshot schema (v1)

```json
{
  "schema_version": "1",
  "created_at": "2026-10-04T12:00:00+00:00",
  "tool_version": "0.1.0",
  "config_hash": "1a2b3c...",
  "project": {"name": "...", "language": "python", "frameworks": ["fastapi"]},
  "surfaces": {
    "http": [
      {
        "probe_id": "POST /login",
        "target": "POST /login",
        "ok": true,
        "error": null,
        "data": {"status": 401, "headers": {...}, "cookies": {...},
                 "body": {...}, "body_kind": "json"}
      }
    ],
    "cli": [],
    "public_api": []
  }
}
```

`baseline.json` and `latest.json` share this schema. `ok: false` entries carry
a transport-level failure (connection refused, timeout); an HTTP error status
is a *successful* capture.

## 5. Data flow of `check`

1. Load config; require `baseline.json` (error 70 if missing).
2. Capture "after" snapshot → `latest.json`.
3. For each surface: match probes by `probe_id`, normalize both sides,
   produce `Change` objects.
4. Load intent (`--intent`, else `.regression-firewall/intent.json`); classify.
5. Assign severity, compute risk score and verdict.
6. Write `report.json` + `report.md`; render console; exit with verdict code.

## 6. Cross-platform rules

- All paths via `pathlib`; no shell strings; probe commands are argv lists.
- `python`/`python3` as `command[0]` is resolved to the running interpreter.
- Subprocess output decoded as UTF-8 with `errors="replace"`; text is
  normalized to `\n` line endings.
- HTTP server processes are terminated (`terminate()` → `kill()` after grace).
- Console output is UTF-8-safe (`sys.stdout.reconfigure(errors="replace")`).
