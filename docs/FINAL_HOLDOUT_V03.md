# Fresh Holdout V0.3 — zod / isort / dateutil

Status: **executed 2026-10-25** (runs 1–2, Windows 11, Python 3.11.9)
Tool version: main @ `ed0a7e2` (post-V0.3, version not yet bumped — this
holdout gates the 0.3.0 release) **plus the parser enhancements made during
authoring** (`js_exports.py`: TypeScript `.js`→`.ts` specifier mapping,
generic function clauses, type-annotated const exports, `type` modifiers in
named lists). The tool code was **identical across both runs**; the
enhancements were committed together with this holdout. This corpus is now
**consumed**.

## Corpus

Frozen in `benchmarks/manifest-holdout-v03.yaml` BEFORE the first run.
Disjoint from all 14 previously used repos.

| Repo | Pinned commit | License | Surface | Why |
|---|---|---|---|---|
| zod | `afdac65e0f80` | MIT | **js_api** (V0.3) | real chained TS barrel: `export *` chains, `.js`→`.ts` specifiers, multi-line named lists with `type` modifiers, generic function clauses |
| isort | `a514c71ed86c` | MIT | **CLI + trace.fs_writes** (V0.3) | formatter CLI writing files in place; opt-in write tracing |
| dateutil | `64914d9bcf98` | Apache-2.0 OR BSD-3 | public API (src/ layout) | core-surface regression guard |

Authoring validation BEFORE freezing (repo-side only, no detection runs):
zod mutations were previewed with the parser itself (55 → 54 symbols on the
rename; signature and added symbol confirmed); the isort sample was
confirmed byte-stable across runs; dateutil's renamed module still imports.

Coverage honesty: the HTTP surface and discovery/`emit-probes` are NOT
covered — V0.3 left HTTP capture/diff untouched, and discovery is exercised
by integration tests against a real Flask app. Recorded as coverage notes,
not pass claims.

## Final result (run 2, POST-FIX VALIDATION)

| Metric | Value |
|---|---|
| Cases ran to verdict | 21 / 21 |
| Detection recall | **100%** (9/9 planted regressions) |
| False-positive rate | **0%** (12/12 controls clean) |
| Severity accuracy | 100% |
| Verdict accuracy | 100% |
| Setup / infra / mutation failures | 0 |

Isolation: `local-scrubbed-env` (**SECURITY LIMITATION**: no Docker).
Full per-case detail: `benchmarks/results/latest.json` (run 2) — numbers
are computed by the runner, never hand-written.

## Run history (honest ledger)

**Run 1 — first execution (2026-10-25).** 20/21 PASS. zod js_api: 7/7
(incl. symbol removal through the chained barrel → CRITICAL/BLOCK,
signature change, symbol added). dateutil: 7/7. isort: 6/7 —
`isort_10_exit_0_to_1` recorded REGRESSION_FIREWALL_FAILURE (one expected
exit flip missing).

**Run 2 — POST-FIX VALIDATION (benchmark authoring fix only; no tool code
changed between runs).** Triage of the run-1 failure: `isort_10` expected
TWO exit flips (targets fix AND help), but isort's `main()` RETURNS
normally instead of raising SystemExit, so under the wrap mutation the fix
probe still exits 0 — **verified empirically** (fix=0, help=1). The tool
correctly detected exactly the one change that could exist.
Re-classified BENCHMARK_ERROR; ground truth corrected to the single help
entry (case history comment in `benchmarks/mutations/isort.yaml`).
Result: **21/21 PASS**, all metrics 100%.

## Findings summary

| # | Root cause class | Item |
|---|---|---|
| 1 | `BENCHMARK_ERROR` | impossible expectation: isort's main() returns instead of raising SystemExit |
| 2 | authoring-phase parser gap (fixed before run 1) | TypeScript `.js`→`.ts` specifier mapping (found on the zod barrel — without it the whole chain resolved to nothing) |
| 3 | authoring-phase parser gap (fixed before run 1) | generic function clauses (`function f<T>(...)`), type-annotated const exports, `type` modifiers in named lists |
| 4 | `CORE_BUG` | **none found** |

The parser gaps (#2, #3) were discovered during authoring by inspecting the
real repository and fixed with tests BEFORE the manifest was frozen — they
are listed here because they are exactly the class of bug this holdout
exists to catch, caught one stage earlier.

## Reproduce

```bash
cp benchmarks/manifest-holdout-v03.yaml benchmarks/manifest.yaml
REGFW_BENCH_WORKSPACE=C:/regfw-bench python -m benchmarks.runner --split holdout
cp benchmarks/manifest-validation-backup.yaml benchmarks/manifest.yaml
```
