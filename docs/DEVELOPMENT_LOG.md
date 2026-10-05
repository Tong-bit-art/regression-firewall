# Regression Firewall — Development Log

Format: reverse-chronological entries; architecture decisions live in
`ARCHITECTURE.md` (D1–D5) and are referenced, not duplicated.

## 2026-10-05 — V0.1 Release Candidate hardening

Feature development frozen. Scope: proving existing capability is reliable.

**P0 — platform & packaging**
- CI matrix reworked: Ubuntu/Windows/macOS × Python 3.11/3.12/3.13 (7 jobs),
  with an explicit build-sdist-and-wheel + install-from-wheel step.
- **Remote CI has NOT been run** (no git repository/remote exists yet); the
  equivalent steps were executed locally: full suite on Python 3.11.9 and
  3.14.3 (136→144 tests), evals 20/20 on both interpreters. Status marker:
  CI CONFIGURED / REMOTE CI NOT YET VERIFIED.
- Packaging: sdist + wheel built with `python -m build`; installed into two
  fresh venvs from wheel and sdist; all six CLI commands verified with no
  repo on `sys.path`. Wheel metadata verified (Requires-Python >=3.9, MIT,
  README description, runner scripts included).

**P1 — reliability**
- Baseline provenance added (`regression_firewall/provenance.py`): every
  snapshot records tool_version, schema_version, created_at, config_hash,
  snapshot_hash (sha256 over captured content), and git state
  (git_available/git_commit/git_dirty) with graceful degradation outside
  git. `check` verifies the stored hash and warns on hand-edited baselines.
- Suspicious re-baseline guard: when the previous check reported BLOCK or
  REVIEW, `baseline` prints a BASELINE TRUST WARNING and refuses without
  `--force`; a forced re-baseline archives the old baseline
  (baseline.previous.json), records the event in provenance, and makes every
  later `check` print the trust warning (console, markdown, report.json).
  Nothing is auto-deleted or auto-overwritten silently.
- Secret redaction extended: private_key/access_key added to the
  secret-name patterns; redaction coverage test now spans the full list
  (Authorization, Cookie, password, passwd, api_key/apikey/api-key,
  access_token, refresh_token, session_token, secret, client_secret,
  private_key, bearer, jwt, nested + list fields).
- False-positive stability: new tests run 10 unchanged checks (CLI) and 10
  unchanged checks (HTTP with timestamps, rotating request-ids, fresh
  session cookies). The HTTP loop caught a real high-frequency FP: epoch
  values under the common `ts` key were never normalized. Fixed by
  extending the temporal key hints (`^ts$`, `_ts$`, `_ms$` — still guarded
  by the epoch range check so business numbers are never masked). Both
  loops now report 0/10.
- README truthfulness: bundled-eval table explicitly labeled synthetic
  ("20/20 bundled V0.1 evaluation cases passed", not real-world accuracy);
  platform status split into tested-locally / designed-compatible / remote
  CI not yet verified; CLI free-text secret limitation documented.
- Dev dependency fix: `flask` added to `[dev]` extras — integration tests
  need it and remote CI would have failed without it (caught by the 3.14
  verification run).

**Verification**
- 144 pytest tests pass (3.11.9); 144 pass on 3.14.3; evals 20/20 on both.
- Wheel rebuilt after all changes; clean-venv install re-verified.

## 2026-10-05 — Release audit (independent review pass)

A full release audit (60+ executable checks in three harness parts plus a
static review) was run against the completed V0.1 before publish.

**Findings & fixes**
- **C1 (Critical) — snapshot secret leakage.** Raw snapshots stored
  Authorization echoes, password/api_key/session_token body fields, and
  session cookie values. Fixed with capture-time redaction
  (`regression_firewall/redact.py`, `redaction.secrets: true` default):
  auth-related headers, all cookie values, and secret-named body fields are
  masked *before storage*; config off-switch trips the config-hash warning.
  Privacy probe now reports zero leaks.
- **H1 (High) — stale-bytecode false PASS.** Same-size, same-second edits
  could pass pyc (mtime, size) validation in tool-managed subprocesses and
  serve old code (observed twice during auditing). Fixed by setting
  `PYTHONDONTWRITEBYTECODE=1` in the managed server, CLI probe, API runner,
  and route runner environments; deterministic 5-attempt regression test.
- **H2 (High) — `ignore.json_paths` did not suppress structural changes.**
  It only skipped value normalization, so `field_removed` at an ignored
  path was still reported. Fixed with a diff-time path filter; documented
  fnmatch semantics (top-level fields need the bare name, not `*.name`).
- **H3 (High) — README claimed `pip install regression-firewall`** while
  the package is not on PyPI. Replaced with honest source-install
  instructions.
- **M1** binary responses now store `{"size": n}` and size changes are
  reported (`value_changed` at `$body`). **M2** an explicit `--intent` path
  that does not exist is now an error (exit 70), not a silent empty intent.
  **M3** subprocess `text=True` calls now pin `encoding="utf-8"`.
  **L1–L6** dead code removals, camelCase `*Time` epoch keys, wildcard-intent
  warning, normalized stdout/stderr previews.
- **Documented (not fixable in tool):** re-baselining after edits cannot be
  distinguished from a legitimate re-baseline (README limitation + SKILL.md
  rule + config-hash warning); ISO date rule masks stable business dates
  like `date_of_birth` (NORMALIZATION.md tradeoff note); cookie value-level
  behavior hidden by default redaction (README limitation + off-switch).

**Verification after fixes**
- 136 pytest tests (incl. 7 new audit regression tests) pass.
- Eval suite: 20/20, recall 100%, FPR 0%, verdict accuracy 100%.
- Audit harness re-run: privacy probe 0 leaks; FP loops 0/10 CLI, 0/5 HTTP;
  stale-bytecode and binary scenarios green; clean-venv install loop green.

## 2026-10-05 — Git repo + first real remote CI runs

Repository initialized and pushed to
`github.com/Tong-bit-art/regression-firewall` (private for now — public
release is gated on real-world validation). Five remote Actions runs
executed before the free Actions quota ran out on the private repo
(macOS minutes bill at 10x).

**Remote-verified so far**
- Ubuntu 3.11/3.12/3.13: green (runs 2-4).
- Windows 3.12/3.13: green (run 4), after fixing a real cross-platform bug:
  the wheel-install step used a glob that PowerShell does not expand
  ("Invalid wheel filename").
- macOS: NOT verified. Every managed HTTP-server start times out (30s) on
  `macos-latest`: the child stays alive, silent, and loopback connects from
  the test process SYN-timeout (dropped, not refused). Diagnostics added to
  the tool (`PYTHONUNBUFFERED`, child `ps` state, `lsof` port probe, effective
  proxies) and a CI debug step (socketfilterfw state + minimal loopback
  roundtrip) are ready for the next run. Also fixed en route: HTTP probes
  and readiness polls now bypass proxy configuration (`ProxyHandler({})`) —
  correct on any machine where a system proxy would otherwise capture
  127.0.0.1 traffic.

**Blocked on**: Actions quota (billing). Next step once unblocked (public
repo or raised limit): re-run, read the macOS diagnostics, fix the runner
issue, get the matrix fully green.

## 2026-10-04 — V0.1 build

**Completed**
- Phase 0: PRD, architecture, behavior model, normalization, risk model,
  eval design, roadmap, skill design docs.
- Phase 1: package skeleton (`regression_firewall`), typed models, config
  loader with validation, argparse CLI (`init`, `discover`, `baseline`,
  `check`, `report`, `explain`), report renderers.
- Phases 2–4: CLI, HTTP (with managed server lifecycle), and Python
  public-API surfaces; public-API extraction via subprocess runner.
- Phase 5: normalization rule engine (uuid, iso datetime, epoch, request id,
  token, temp path, duration, float precision, whitespace, ANSI).
- Phase 6: intent file format + deterministic expectation matcher
  (EXPECTED / UNEXPECTED / UNCERTAIN).
- Phase 7: severity tables, additive risk score, verdict rules with
  consistency floors.
- Phase 8: 20 deterministic eval cases + runner + metrics.
- Phase 9: SKILL.md (agent contract + anti-gaming rules).
- Phase 10: README, LICENSE, contributing/security/changelog, examples
  (FastAPI, Flask, CLI, Python library), GitHub Actions CI.

**Verification**
- 128 pytest tests (unit + integration + eval suite) pass on Windows 11 /
  Python 3.11.
- Eval suite: 20/20 cases — recall 100%, FPR 0%, verdict accuracy 100%.
- End-to-end smoke tests against real frameworks: FastAPI and Flask
  examples both run the full baseline → mutate → check loop with the
  tool-managed server lifecycle (these caught the probe-body bug).

**Decisions** (details in ARCHITECTURE.md)
- D1 Python ≥ 3.9 core CLI. D2 PyYAML as the only runtime dependency.
- D3 raw capture + normalize-at-diff-time; `config_hash` warning.
- D4 subprocess isolation for public-API extraction; managed HTTP server.
- D5 deterministic classification/scoring; no LLM in the pipeline.
- Deviations from the brief's suggested tree: `normalize/` merged
  json/text rule files into `engine.py` + `rules.py` (small files, one
  concern each); `discovery/framework.py` merged into `discovery/project.py`
  (detection is one cohesive step); added `capture/server.py` for HTTP
  server lifecycle and `models/` split kept as designed.

**Problems found & fixed during development**
- Circular import when `diff.engine` dispatched to surface diff modules that
  imported it back; restructured so `diff/__init__.py` owns surface dispatch
  and `diff/engine.py` stays a pure JSON-diff helper.
- `score_floored` was set whenever a verdict *rule* fired even when the raw
  score already exceeded the threshold; now it is set only when a floor
  actually raised the score, so the flag stays honest.
- Duration normalization did not apply to numeric values (only strings).
- Value-level epoch timestamps (`time.time()` floats) were not normalized;
  `looks_like_epoch` now covers floats and the temporal-key rule applies to
  both int and float.
- Temp-path masking in *text* replaced only the temp-dir root, leaving
  random file names (e.g. PID-suffixed temp files) as diffs; token-level
  whole-path masking now runs first, mirroring the JSON rule.
- `ManagedServer.start` crashed with `AttributeError` when the server
  process exited during startup (`stop()` had cleared the process handle
  before the exit code was read).
- Intent paths did not match change paths: changes carry `$.user.name`
  while intent files say `user.name`; the matcher strips the `$.` prefix.
- **HTTP probe bodies were silently dropped during config parsing**
  (a leftover `isinstance(x, MISSING.__class__)` guard evaluated as
  `isinstance(x, object)` — always true). Caught by smoke-testing the
  FastAPI example with a real framework: the login probe got a body-less
  422 from FastAPI instead of the handler's 401. Fixed + regression tests
  (`test_probe_body_roundtrip`); eval cases had missed it because their
  stdlib servers never validate bodies.
- Example configs were named `regression-firewall.yml` (no leading dot) and
  were not discovered; the loader now accepts both dotted and undotted
  variants.
- pytest collection broke when passing both test directories as arguments
  (two `conftest` modules on `sys.path`); helpers moved from conftest into
  fixtures so `pytest tests` and `pytest tests/unit tests/integration` both
  work.

**Technical debt / known limitations**
- Public-API surface is Python-only for now (JS/TS in V0.2).
- HTTP discovery needs explicit `discover.app` config or manual probes.
- CLI generated-file tracking uses an explicit watch list.
- Route discovery and API introspection import user code in a subprocess —
  sandboxing is out of scope; documented risk.

**Next**
- Community feedback pass on report wording; JS/TS surface (V0.2).
