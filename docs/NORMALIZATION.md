# Regression Firewall — Normalization

Version: 0.1 (2026-10-04)

Normalization exists for one reason: **false positives are the primary
failure mode of this tool**. Anything that legitimately varies between two
runs of identical code must not surface as a behavior change. Anything that
is a real contract must survive normalization untouched.

## 1. When it runs

Captures are stored raw. The diff engine builds a `Normalizer` from the
current config and applies it to **both** sides (baseline and latest) before
comparing. Re-checking old baselines after tuning normalization config is
therefore safe.

## 2. Rule catalog

Rules apply to JSON values (with the enclosing key name and JSON path as
context), header maps (header name as key), cookie maps, and plain text
(stdout/stderr). "Inline" versions run on text where the pattern may appear
mid-line.

| Rule (config key) | Matches | Replaced with | Context guard |
|---|---|---|---|
| `uuid` | Canonical UUID v1–v8 shape `8-4-4-4-12` hex | `<UUID>` | value-shape only |
| `iso_datetime` | ISO 8601 date / datetime (`2026-10-04`, `2026-10-04T12:00:00Z`, `+02:00`, space-separated) | `<DATETIME>` | value-shape only |
| `epoch_timestamps` | 10- or 13-digit epoch (s/ms) in plausible range | `<TIMESTAMP>` | **key must look temporal** (`timestamp`, `_at`, `date`, `time`, ...) |
| `request_ids` | Key/header containing `request_id`, `correlation_id`, `trace_id`, `x-request-id` | `<REQUEST_ID>` | key hint |
| `tokens` | Key/header containing `token`, `secret`, `nonce`, `api_key`, `password`, `session`, `csrf`, `auth` | `<TOKEN>` | key hint |
| `temp_paths` | String containing a known temp-dir prefix (`tempfile.gettempdir()`, `/tmp/`, `AppData\Local\Temp`, ...) and looking like a path | `<TEMP_PATH>` | prefix match |
| `durations` | Key containing `duration`, `elapsed`, `latency`, `took` | `<DURATION>` | key hint |
| `float_precision` | Floats rounded to N decimals (default 6), `-0.0 → 0.0` | numeric | — |
| `whitespace` | (text) `\r\n → \n`, trailing whitespace per line stripped | text | — |
| `ansi` | (text) ANSI CSI/OSC escape sequences | removed | — |

Placeholder order matters: value-shape rules (uuid, iso) run before key-hint
rules; a UUID in a `request_id` key becomes `<UUID>` (shape wins, same
effect for diffing).

## 3. Anti-over-normalization guards

- Key-hint rules never fire on business-looking keys (`id`, `user_id`,
  `order_no`). A plain numeric ID stays a plain numeric ID.
- Value-shape rules are anchored (the whole value must match), so
  `"abc123"` under a neutral key is untouched. Under a secret-ish key, any
  value is masked — deliberate, so secrets never leak into reports.
- Temp-path detection uses *known temp roots only*, never a bare substring
  `temp` (so `templates/index.html` is untouched).
- Booleans are never rounded; strings are never number-coerced.
- Arrays are compared positionally; **no sorting** — order is behavior.

## 4. Config

```yaml
normalization:            # every rule on by default
  uuid: true
  iso_datetime: true
  epoch_timestamps: true
  request_ids: true
  tokens: true
  temp_paths: true
  durations: true
  float_precision: true
  whitespace: true
  ansi: true

ignore:
  headers:                # dropped from both sides before diffing
    - date
    - content-length
  json_paths:             # suppresses ALL reported changes at matching paths
    - "*.debug_trace"
```

`ignore.json_paths` matches the dotted change path with fnmatch (`*` crosses
dots) and suppresses every change category at that path, structural ones
(`field_removed`, `field_type_changed`, ...) included. Standard fnmatch
semantics apply: `*.debug_trace` matches the nested path
`response.debug_trace` but **not** a top-level field named `debug_trace`
(use the bare name for that). Ignoring a path is a trust decision — the
check report warns whenever the configuration changed since the baseline.

## 6. Known tradeoff: stable business dates

The `iso_datetime` rule is value-shaped and key-agnostic, so a *stable*
business date such as `date_of_birth: "1990-05-01"` is also masked
(`<DATETIME>`), and changes to it will not be reported. This buys silence
for the far more common generated-date case. If a project treats such
fields as behavior, disable the rule (`normalization.iso_datetime: false`)
or narrow the noise with `ignore.json_paths` elsewhere.

Defaults for `ignore.headers`: `date`, `content-length` (the latter is fully
derived from the body, which is diffed directly). `x-request-id` style
headers do not need ignoring — the `request_ids` rule masks them.

## 5. Extensibility (V0.1)

Rules are plain functions registered in a ordered list in `normalize/rules.py`
with an on/off switch in config. Custom user rules are a V0.2 item (plugin
point reserved by the registry shape, nothing speculative built).


## 7. Capture-time redaction (separate from normalization)

Normalization runs at diff time and never touches stored data. Snapshots,
however, are plain JSON on disk, so secrets are removed **at capture time**
(`redaction.secrets: true` by default): auth-related headers, all cookie
values, and body fields with secret-ish names become `<REDACTED>`. See
`docs/BEHAVIOR_MODEL.md` and `SECURITY.md`.
