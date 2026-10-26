# Proposal — Plugin API for Custom Behavior Surfaces

Status: **PROPOSAL — not implemented.** Deferred from V1.0 until a driving
need exists. This document exists so that the eventual implementation starts
from a written design instead of being re-derived under pressure.

## 1. Motivation

Users eventually want behavior surfaces the tool does not ship: message
queues, Redis, gRPC, custom protocols. Today the only options are forking or
approximating with CLI probes. A plugin mechanism would let a surface be
installed as a package and configured like a built-in one.

## 2. What a surface actually is (from the four built-ins)

A surface is, concretely, five coupled pieces:

1. **Config section** — a `<name>` block under `surfaces:` with validated
   fields (`config/schema.py`), included in the config hash, and rejected
   when unknown (today's strictness is a security property).
2. **Capture** — a function `(section, project_root) -> (list[ProbeCapture],
   warnings)`; some surfaces shell out to a subprocess with scrubbed env
   (see `capture/base.py` for the conventions: `PYTHONDONTWRITEBYTECODE`,
   interpreter resolution, tracer injection).
3. **Diff** — a function `(before, after, config, make_change) -> list[Change]`
   with categories registered in `scoring/severity.py` and
   `intent/matcher.py`.
4. **Report/UI** — the surface name appears in console/Markdown/JSON
   (currently stringly-typed per surface in three renderers).
5. **Docs** — a BEHAVIOR_MODEL section with honest scope/limitations.

## 3. The hard problems (why this is not a weekend feature)

- **Config strictness vs. extensibility.** Unknown `surfaces:` keys are
  rejected loudly — that catches typos and YAML surprises, which for a
  verification tool is a feature. Plugins need an opt-in escape hatch that
  does not silently loosen validation for everyone.
- **Trust.** A plugin runs project code at capture time (all surfaces do),
  but a *third-party* plugin additionally runs at CONFIG PARSE time and can
  alter verdict semantics (severities, classifications). The anti-gaming
  story must extend to plugins: what stops a malicious plugin from
  classifying everything as expected?
- **Determinism contract.** Every built-in surface is deterministic. The
  plugin contract must make determinism a documented requirement and the
  no-evidence guard must apply to plugin captures automatically.
- **Snapshot coupling.** Capture payloads are stored verbatim in snapshots;
  plugin payloads must be forward/backward compatible or snapshots break.

## 4. Recommended shape (when implemented)

- **Registry, not hooks.** Built-in surfaces stay internal. Plugins
  register through Python entry points (`regression_firewall.surfaces`) and
  are DISABLED unless the config enables them explicitly:

  ```yaml
  plugins:
    - name: redis-surface      # entry-point name
      enabled: true
      # plugin-specific config lives under the plugin's own key
  ```

- **Contract (typed, in `regression_firewall/surface_api.py`)**: a
  `Surface` protocol with `config_schema` (a dataclass + parser), `capture`,
  `diff`, `categories` (name → default severity, classification), and
  `docs_url`. The engine treats it exactly like a built-in: same guards,
  same report paths, same intent matching.
- **Security**: plugin modules are imported in a subprocess (like the
  api-runner), never in-process; plugins CANNOT alter verdict rules, score
  floors, or the guards — only contribute captures and categories.
- **Evidence requirement**: ship one first-party example surface through
  the plugin path (dogfooding), plus an eval case, before stabilizing.

## 5. Explicitly rejected

- LLM-assisted classification inside plugins.
- Plugins that can weaken guards (re-baseline, no-evidence, post-hoc) or
  edit reports.
- Auto-enabling plugins found on the machine.

## 6. Suggested phasing

1. Refactor the four built-in surfaces onto an internal `Surface` protocol
   (no behavior change, full test suite green) — this alone de-risks
   everything else and can ship without any plugin support.
2. Add the registry + entry-point loading behind explicit config opt-in.
3. Ship one first-party example surface + docs + eval case.
4. Only then mark the contract stable.
