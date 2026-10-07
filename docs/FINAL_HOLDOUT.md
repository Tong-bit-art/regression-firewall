# Fresh Final Holdout

**Frozen implementation commit:** `8428a5b13cdd9d54807ee17a23ddbaef61173454`
**Frozen date:** 2026-10-07
**Status:** RUN ONCE (original results in `docs/FINAL_EVIDENCE_REPORT.md`);
post-fix validation appended 2026-10-07; **this holdout is consumed** — per
the rules below it moves to the validation corpus, and a NEW fresh holdout
must be selected before the next release cycle.

## Selection criteria

These repositories were selected because they have NEVER been used for:
- development of Regression Firewall
- debugging of Regression Firewall
- benchmark or mutation design
- rule adjustment or threshold tuning
- any prior validation or testing

## Repositories (frozen before first run)

| Repo | URL | Commit | License | Type | Surface |
|---|---|---|---|---|---|
| bottle | [bottlepy/bottle](https://github.com/bottlepy/bottle) | `cbd569c447` | MIT | Web framework (library) | public_api |
| urllib3 | [urllib3/urllib3](https://github.com/urllib3/urllib3) | `a164d79c8c` | Apache-2.0 | HTTP library | public_api |
| packaging | [pypa/packaging](https://github.com/pypa/packaging) | `2aada00b15` | Apache-2.0 OR BSD-2-Clause | Library | public_api |

## Mutation cases (frozen before first run)

Each repo has 5 cases: 3 controls + 2 planted regressions.
Ground truth was authored before the first run and stored in
`benchmarks/mutations/<repo>.yaml`.

| Repo | Control | Non-behavior | Symbol removed | Signature changed | Symbol added |
|---|---|---|---|---|---|
| bottle | ×3 | ✓ | ✓ (tob → _tob) | ✓ (makelist + separator) | ✓ (benchmark_added) |
| urllib3 | ×3 | ✓ | ✓ (encode_multipart_formdata) | ✓ (request + new_required_param) | ✓ (benchmark_added) |
| packaging | ×3 | ✓ | ✓ (parse → _parse) | ✓ (parse + strict) | ✓ (benchmark_added) |

## Rules

- This holdout is run EXACTLY ONCE.
- The original results are final, regardless of pass/fail.
- If a critical bug is found: fix it, report the ORIGINAL holdout result,
  move this holdout to the validation corpus, and select a NEW fresh holdout.
- Do NOT re-run after fixes and call it a holdout.
- Do NOT modify ground truth after seeing results.

## Post-fix validation (2026-10-07, later same day)

Re-running the same mutations after fixes is **post-fix validation, not a
holdout**. It is recorded separately and must not be cited as holdout
numbers. Result: **7/7 per repo — 3/3 planted regressions detected, 0 false
positives** (bottle, urllib3, packaging).

Benchmark fixes applied before this re-run (recorded in full; no
ground-truth tuning):

1. `manifest-holdout.yaml` wrote `setup_commands` as a plain string; the
   runner iterated it character-by-character into `python -` (empty stdin →
   exit 0 → silent no-install). Bottle only survived because it is a single
   file at the repo root. Fixed to argv lists; the runner now rejects string
   commands loudly.
2. The per-case restore (`git clean -fdqx`) deleted build-generated files
   (urllib3's `src/urllib3/_version.py`), breaking every later capture. The
   runner now re-applies the repo setup per case.
3. The packaging probes covered only the top-level `packaging` module while
   the mutations edit `packaging.version`; the missing probe was added.
4. Tool fixes (not ground truth): standard src-layout import root;
   unresolvable `__all__` entries classified as removals; module-dict
   enumeration behind restrictive `__dir__`; no-evidence guard (a probe that
   fails at both baseline and check can no longer PASS silently).
5. The original urllib3 signature mutation inserted a second `*` into the
   signature and produced a SyntaxError (invalid code). It was corrected
   (insert the required keyword-only parameter after the existing `*,`).
   The ORIGINAL holdout result for that case (miss) stands as recorded.
