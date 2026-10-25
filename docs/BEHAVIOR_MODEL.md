# Regression Firewall — Behavior Model

Version: 0.1 (2026-10-04)

This document defines what "behavior" means to Regression Firewall, how it is
captured, and how differences become structured `Change` objects.

## 1. Probes and captures

A **probe** is a configured, repeatable behavior elicitation: an HTTP request,
a CLI invocation, or a module introspection. Running a probe produces a
**capture** — raw, timestamp-free, normalized *later*, never at capture time.

A capture that reached the subject is `ok: true` even if the subject returned
an error status (a `500` is behavior). `ok: false` means the probe could not
reach the subject at all (connection refused, timeout, import crash) — that
state flip is itself a high-severity behavior change.

## 2. Surfaces

### Surface A — HTTP

Probe fields: `id`, `method` (GET/POST/PUT/PATCH/DELETE), `path`, `headers`,
`body` (object → JSON-encoded, string → verbatim), `follow_redirects`,
`timeout`.

Capture payload:

```json
{
  "status": 401,
  "headers": {"content-type": "application/json",
              "authorization": "<REDACTED>"},
  "cookies": {"session": "<REDACTED>"},
  "body": {"error": "invalid_credentials"},
  "body_kind": "json"        // json | text | binary | none
}
```

With `redaction.secrets: true` (the default) auth-related headers, all
cookie values, and secret-named body fields are masked **before the capture
is stored**; snapshots are safe to attach to bug reports. Binary bodies
store `{"size": n}` instead of bytes, so size changes stay observable.

Notes:
- `Set-Cookie` values move from `headers` into `cookies` (name → first value).
- JSON bodies are parsed; unparseable JSON stays `text`.
- An optional `server.command` lets the tool start the app itself, wait until
  it answers on `ready_path`, run probes, and shut it down. Without it the
  server must already be running at `base_url`.

### Surface B — CLI

Probe fields: `id`, `command` (argv list), `cwd`, `env`, `files` (watch list),
`timeout`.

Capture payload:

```json
{
  "exit_code": 0,
  "stdout": "Deployment complete",
  "stderr": "",
  "files": {
    "out/receipt.json": {"exists": true, "sha256": "…", "size": 210}
  }
}
```

Generated-file tracking uses the explicit watch list: entries record
existence, size, and content hash, so `file_created` (absent → present),
`file_deleted`, and `file_modified` (hash change) are all detectable.
Discovery of *unknown* generated files is V0.2 work (roadmap).

### Surface C — Public API (Python)

Probe fields: `id`, `module` (import name), `include_private`.

Capture payload (produced by a subprocess runner):

```json
{
  "symbols": {
    "Client": {"kind": "class", "signature": "(self, retries=3)"},
    "retry": {"kind": "function", "signature": "(func, attempts=3)"}
  },
  "submodules": ["samplelib.errors"],
  "exports": ["Client", "retry"]
}
```

Rules: if the module defines `__all__`, its order is the export list and its
names are the symbols; otherwise public names (`no leading underscore`,
dunders excluded) are used. Submodules are listed from `__path__`. Signatures
come from `inspect.signature` (unavailable ones recorded as such). Kinds:
`function`, `class`, `module`, or the constant's type name.

### Surface D — JS/TS API (static)

Probe fields: `id`, `file` (project-relative entry file). Nothing executes:
the file is parsed statically (`js_exports.py`), so this surface works even
when the package cannot run in the capture environment.

Capture payload (symbols dict, re-exports resolved to depth 3):

```json
{
  "file": "src/index.ts",
  "symbols": {
    "createApp": {"kind": "function", "signature": "(name, options?)",
                   "origin": "src/entry.ts"},
    "default": {"kind": "default", "signature": null, "origin": "src/entry.ts"}
  }
}
```

Covered syntax: ESM `export function/class/const/let/var/interface/type/enum`,
`export default`, alias lists (`export {a as b}`), CommonJS
`exports.NAME` / `module.exports.NAME`, and relative re-exports
(`export {x} from`, `export * from`, `export * as ns from`). Comments and
string contents are stripped before matching. Deliberately NOT understood
(invisible, never guessed): minified code, dynamic exports, destructured
`export const {a} = ...`, bundler path aliases, object-literal
`module.exports = {...}`, class members, `export =`.

## 3. Change object

Every detected difference is one structured `Change`:

| Field | Meaning |
|---|---|
| `change_id` | Stable short hash of (surface, target, category, path) |
| `surface` | `http` / `cli` / `public_api` |
| `target` | Probe target, e.g. `POST /login`, `deploy`, `samplelib.RetryPolicy` |
| `category` | One of the tables below |
| `path` | JSON path inside the payload, e.g. `$.user.email` (HTTP only) |
| `before` / `after` | Normalized values (missing side rendered as `null` + flag) |
| `classification` | `EXPECTED` / `UNEXPECTED` / `UNCERTAIN` |
| `severity` | `INFO` / `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` |
| `confidence` | 0–1, from the category class (structural 0.95, value-level 0.75, state 0.9) |
| `note` | Matched intent note, when expected |
| `evidence` | Category-specific extras (e.g. status transition kind) |
| `description` | One-line human summary |

## 4. Categories and default severities

### HTTP

| Category | Default severity | Classification when unmatched |
|---|---|---|
| `status_changed` (success → error) | HIGH | UNEXPECTED |
| `status_changed` (error → error, other transitions) | MEDIUM | UNEXPECTED |
| `status_changed` (success → success) | MEDIUM | UNEXPECTED |
| `field_removed` | HIGH | UNEXPECTED |
| `field_added` | LOW | UNCERTAIN |
| `field_type_changed` | MEDIUM | UNEXPECTED |
| `response_shape_changed` (root container type) | MEDIUM | UNEXPECTED |
| `value_changed` | LOW | UNCERTAIN |
| `list_size_changed` | LOW | UNCERTAIN |
| `content_type_changed` | MEDIUM | UNEXPECTED |
| `header_changed` | LOW | UNCERTAIN |
| `cookie_changed` | MEDIUM | UNEXPECTED |
| `capture_error` (reachability flipped) | HIGH | UNEXPECTED |

### CLI

| Category | Default severity | Classification when unmatched |
|---|---|---|
| `exit_code_changed` (0 → non-zero) | HIGH | UNEXPECTED |
| `exit_code_changed` (other transitions) | MEDIUM | UNEXPECTED |
| `stdout_changed` | LOW | UNCERTAIN |
| `stderr_changed` | LOW | UNCERTAIN |
| `file_created` | MEDIUM | UNCERTAIN |
| `file_deleted` | HIGH | UNEXPECTED |
| `file_modified` | MEDIUM | UNCERTAIN |
| `fs_write_added` (trace) | MEDIUM | UNCERTAIN |
| `fs_write_removed` (trace) | MEDIUM | UNCERTAIN |
| `env_read_added` (trace) | LOW | UNCERTAIN |
| `env_read_removed` (trace) | LOW | UNCERTAIN |
| `db_query_added` (trace.sqlite) | MEDIUM | UNCERTAIN |
| `db_query_removed` (trace.sqlite) | MEDIUM | UNCERTAIN |
| `db_query_count_changed` (trace.sqlite) | LOW | UNCERTAIN |
| `db_table_written_added` (trace.sqlite) | MEDIUM | UNCERTAIN |
| `db_table_written_removed` (trace.sqlite) | MEDIUM | UNCERTAIN |
| `runtime_regressed` (performance) | MEDIUM | UNCERTAIN |
| `capture_error` | HIGH | UNEXPECTED |

Tracing (`trace.fs_writes` / `trace.env_reads`) is opt-in per probe and
Python-only: a `sitecustomize.py` injected via PYTHONPATH records write
paths and env-var NAMES (values never captured; `io.open` and `builtins.open`
are both wrapped; `os.fdopen`-style fd writes are invisible). Write paths
under the project root are stored project-relative.

`trace.sqlite` records stdlib sqlite3 usage through the documented
`factory` subclass hook (C types cannot be monkeypatched, but they are
subclassable): `Connection.execute/executemany/executescript` and
`Cursor.execute/executemany` are traced. Statements are normalized to
SHAPES at capture time (string/numeric literals -> `?`, `IN`-lists
collapsed, comments and whitespace removed) so a data change never looks
like a query-set change; per-shape counts are recorded and their change is
a LOW signal that forces a human review (the N+1 signal: an existing
query now runs a different number of times). Write targets (INSERT /
UPDATE / DELETE / REPLACE / CREATE / DROP / ALTER) are extracted
best-effort. NOT traced (invisible, never guessed): other drivers, ORMs
(SQLAlchemy etc.), network databases, `executemany` row multiplicity,
connections created with a custom `factory`.

## Performance measurement (opt-in, V0.6)

`probe.performance` (`enabled`, `repeat` = 5, `warmup` = 1, `max_ratio` =
2.0) runs the command `warmup` untimed times, then `repeat` timed times;
the captured behavior comes from the last run and the sorted durations plus
their median (ms) are stored. At diff time, `median_after / median_before >
max_ratio` is `runtime_regressed` — MEDIUM, UNCERTAIN, so it forces a human
review and can never auto-BLOCK. Timing is machine-dependent: budgets are
ratios (never absolute milliseconds), and the baseline stays machine-local.
Traces accumulate over all runs on both sides, so trace counts remain
comparable. Default: off.
### Public API

| Category | Default severity | Classification when unmatched |
|---|---|---|
| `symbol_removed` | CRITICAL | UNEXPECTED |
| `symbol_added` | INFO | UNCERTAIN |
| `signature_changed` | MEDIUM | UNEXPECTED |
| `export_changed` (`__all__`) | MEDIUM | UNEXPECTED |
| `capture_error` | HIGH | UNEXPECTED |

### JS/TS API

| Category | Default severity | Classification when unmatched |
|---|---|---|
| `symbol_removed` | CRITICAL | UNEXPECTED |
| `symbol_added` | INFO | UNCERTAIN |
| `signature_changed` | MEDIUM | UNEXPECTED |
| `export_changed` (kind flip) | MEDIUM | UNEXPECTED |
| `capture_error` (entry file missing) | HIGH | UNEXPECTED |

Severities are overridable per category (or per `surface:category`) in config.
The *unmatched* classification column is the deterministic default; the
intent matcher can upgrade a change to `EXPECTED` but never downgrades an
`UNEXPECTED` to `UNCERTAIN` by itself.

## 5. JSON structural diff

Bodies are compared recursively by JSON type (`null`, `boolean`, `number`,
`string`, `array`, `object`):

- Object: key removed → `field_removed`; key added → `field_added`; common
  keys recurse.
- Array: length change → `list_size_changed`; elements recurse positionally.
- Scalars: type change → `field_type_changed` (at the root: `response_shape_changed`);
  same-type value difference → `value_changed`.
- `1` and `1.0` are equal numbers; `true` and `1` are different types.
- Floats are rounded (default 6 decimals) before comparison to absorb FP noise.

Paths are dotted (`$.user.email`), array items indexed (`$.items[0].id`).
