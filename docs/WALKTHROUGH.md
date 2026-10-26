# Walkthrough — one complete loop

This is a single, real run of the whole workflow on a tiny Flask app. Every
output below was produced by the actual tool (2026-10-26, v0.4.1); only the
paths are abbreviated. Expected duration: under a minute.

## 0. The project

```python
# app.py
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/api/health")
def health():
    return jsonify(status="ok", version="1.0")


@app.route("/api/users/<int:uid>")
def user(uid):
    return jsonify(id=uid, name="alice", plan="free")
```

## 1. `init` — one command wires everything

```text
$ regression-firewall init
Regression Firewall
  Created: .regression-firewall.yml
  Created: .regression-firewall/
  Detected project: walkthrough (python / flask)
  Auto-configured: 1 HTTP probe(s) generated from app:app (flask); 2 parameterized route(s) excluded
  Auto-configured: managed Flask server configured
```

`init` imported the app (in an isolated subprocess), generated the probe for
`GET /api/health` from its real routes, configured a managed Flask server
with a `{port}` base URL, and excluded the parameterized route
(`/api/users/<int:uid>` needs a concrete value — set one by hand, or use the
OpenAPI import).

## 2. Baseline — record what the code *currently* does

```text
$ regression-firewall baseline
  Provenance: commit 9fff54b1eeb8, working tree dirty
  Saved: .regression-firewall/baseline.json
```

## 3. The change

Suppose an agent (or you) reworks `/api/health` and quietly drops the
deprecated `version` field. Tests for the new behavior pass. Nothing fails
anywhere. Then:

## 4. `check` — the old behavior gets a verdict

```text
$ regression-firewall check
...
Changes: 0 expected, 1 unexpected, 0 uncertain
Changed files since baseline (git hint): 2
  app.py

Unexpected Changes

  HIGH  GET /api/health  field_removed  [$.version]
      1.0 -> <absent>
      Why this matters: Existing consumers may read this field; removing it
      breaks them at runtime, not at compile time.
      Requested? no evidence in intent
      Confidence: 95%

Risk Score: 70 / 100
Verdict: BLOCK
1 high-risk unintended change(s) detected.

Recommended action:
  Restore the removed field, or agree a deprecation window with consumers.

(exit code: 3)
```

**BLOCK means the task is not complete.** In CI the job fails; for an
agent, the SKILL.md contract forbids declaring success.

## 5. `explain` — full detail for one change

```text
$ regression-firewall explain fb037dcf99d9
Change fb037dcf99d9
  Surface:   http
  Target:    GET /api/health
  Category:  field_removed
  Path:      $.version
  Class:     unexpected
  Severity:  high
  Confidence: 95%
  Before:    1.0
  After:     null
```

## 6. `status` — orientation at any point

```text
$ regression-firewall status
  Surfaces: http 1 probe(s), cli 0 probe(s), public_api 0 probe(s), js_api 0 probe(s)
  Baseline: captured 2026-10-26T16:38:05+00:00, commit 9fff54b1eeb8, 1 probe(s), integrity OK
  Intent:  none on file (every detected change is treated as unrequested)
  Last check: BLOCK (score 70/100) at 2026-10-26T16:38:07+00:00
    changes: 0 expected, 1 unexpected, 0 uncertain
  Audit journal: 2 event(s)
```

## 7. Intent — declare what was *requested*

If removing the field was genuinely the task, record that as intent (the
path is written **without** the `$.` prefix) and accept the post-hoc entry
explicitly — the tool records that the intent appeared only after the
behavior was observed:

```json
{
  "schema_version": 1,
  "task": "Drop the deprecated version field from /api/health.",
  "expected_changes": [
    {
      "surface": "http",
      "target": "GET /api/health",
      "category": "field_removed",
      "path": "version",
      "note": "deprecated field, consumers notified"
    }
  ]
}
```

```text
$ regression-firewall check --accept-post-hoc-intent
WARNING: post-hoc intent entries were accepted via --accept-post-hoc-intent
         (explicit acknowledgement recorded in intent_audit)

Changes: 1 expected, 0 unexpected, 0 uncertain
Expected Changes
  ✓ EXPECTED  GET /api/health  field_removed  1.0 -> <absent>

(exit code: 0)
```

Without `--accept-post-hoc-intent` the run stays at REVIEW — a late intent
file can never silently reclassify something the tool already reported.

## What you just saw

| Piece | What it does |
|---|---|
| `init` | detected the app, generated verified probes, configured the server |
| `baseline` | froze pre-change behavior with git provenance + integrity hash |
| `check` | structural diff, classification, explainable score, verdict |
| `explain` | one change in full detail |
| `status` | orientation: what exists, what was captured, last verdict |
| intent + audit | the difference between "requested" and "observed", enforced |

Next: point the [GitHub Action](CI.md) at your repository, or read
[BEHAVIOR_MODEL.md](BEHAVIOR_MODEL.md) for what each surface captures.
